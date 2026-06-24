"""
ASDA v1 — RAG Pipeline
======================
Phase 1: Clone → Walk → AST Chunk → Embed → Store → Retrieve

Usage:
    from rag import RAGPipeline
    rag = RAGPipeline()
    rag.index(repo_url, github_token)
    chunks = rag.retrieve("fix the divide by zero bug in utils")
"""

import os
import ast
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer


# ── Constants ────────────────────────────────────────────────────────────────

EMBED_MODEL   = "all-MiniLM-L6-v2"
CHROMA_DIR    = ".asda/chroma"
COLLECTION    = "codebase"
TOP_K         = 6
MAX_CHUNK_LEN = 6000   # characters — skip unusually large generated files
FALLBACK_LINES = 60    # lines per chunk when AST parse fails

SKIP_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "env",
    "node_modules", "dist", "build", ".mypy_cache",
    ".pytest_cache", "migrations", ".asda",
}

SKIP_FILES = {
    "setup.py", "conf.py",          # usually boilerplate
}


# ── RAG Pipeline ─────────────────────────────────────────────────────────────

class RAGPipeline:
    """
    Full RAG pipeline for ASDA v1.

    Lifecycle
    ---------
    1. index(repo_url, token)   — clone repo, chunk, embed, persist to ChromaDB
    2. retrieve(task, k)        — embed task, return top-k relevant chunks
    """

    def __init__(self):
        self.model      : Optional[SentenceTransformer] = None
        self.collection : Optional[chromadb.Collection] = None
        self.repo_path  : Optional[Path] = None
        self._loaded    = False

    # ── Public API ────────────────────────────────────────────────────────────

    def index(self, repo_url: str, github_token: str) -> dict:
        """
        Clone `repo_url` and build a ChromaDB index of the codebase.

        Returns a summary dict:
            { files: int, chunks: int, skipped: int, repo_path: str }
        """
        print("\n[ASDA] Loading embedding model...")
        self._load_model()

        print("[ASDA] Cloning repository...")
        self.repo_path = self._clone(repo_url, github_token)
        print(f"[ASDA] Cloned to {self.repo_path}")

        print("[ASDA] Walking and chunking codebase...")
        chunks, stats = self._build_chunks(self.repo_path)

        print(f"[ASDA] {stats['files']} files → {len(chunks)} chunks "
              f"({stats['skipped']} files skipped)")

        print("[ASDA] Embedding and indexing chunks...")
        self._store(chunks)

        self._loaded = True
        print(f"[ASDA] Index ready — {len(chunks)} chunks in ChromaDB\n")

        return {
            "files":     stats["files"],
            "chunks":    len(chunks),
            "skipped":   stats["skipped"],
            "repo_path": str(self.repo_path),
        }

    def retrieve(self, task: str, k: int = TOP_K) -> list[dict]:
        """
        Embed `task` and return the top-k most relevant code chunks.

        Each chunk:
            { text, file, name, lines, score }
        """
        if not self._loaded:
            raise RuntimeError(
                "Index not built. Call .index(repo_url, token) first."
            )

        query_vec = self.model.encode([task])[0].tolist()

        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=min(k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text":  doc,
                "file":  meta.get("file", ""),
                "name":  meta.get("name", ""),
                "lines": meta.get("lines", ""),
                "score": round(1 - dist, 4),   # cosine similarity
            })

        return chunks

    def get_file(self, relative_path: str) -> Optional[str]:
        """Read a file from the cloned repo. Returns None if not found."""
        if not self.repo_path:
            return None
        full = self.repo_path / relative_path
        if full.exists():
            return full.read_text(encoding="utf-8", errors="replace")
        return None

    # ── Clone ─────────────────────────────────────────────────────────────────

    def _clone(self, repo_url: str, token: str) -> Path:
        """
        Clone the repo into a temp directory.
        Injects the PAT into the URL for private repo support.
        """
        dest = Path(tempfile.mkdtemp(prefix="asda_repo_"))

        # Inject token: https://token@github.com/owner/repo.git
        if token and "github.com" in repo_url:
            repo_url = repo_url.replace(
                "https://", f"https://{token}@"
            )
            if not repo_url.endswith(".git"):
                repo_url += ".git"

        result = subprocess.run(
            ["git", "clone", "--depth=1", repo_url, str(dest)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(
                f"Git clone failed:\n{result.stderr.strip()}"
            )

        return dest

    # ── Walk + Chunk ──────────────────────────────────────────────────────────

    def _build_chunks(self, repo_path: Path) -> tuple[list[dict], dict]:
        """Walk the repo and return all chunks + stats."""
        chunks  = []
        files   = 0
        skipped = 0

        for filepath in self._walk(repo_path):
            files += 1
            try:
                src = filepath.read_text(encoding="utf-8", errors="replace")
                file_chunks = self._chunk_file(filepath, src, repo_path)
                chunks.extend(file_chunks)
            except Exception:
                skipped += 1

        return chunks, {"files": files, "skipped": skipped}

    def _walk(self, root: Path):
        """Yield .py files, skipping irrelevant directories."""
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune skip dirs in-place so os.walk doesn't descend
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if fname.endswith(".py") and fname not in SKIP_FILES:
                    yield Path(dirpath) / fname

    def _chunk_file(
        self, filepath: Path, src: str, repo_root: Path
    ) -> list[dict]:
        """
        Split a Python file into chunks at function/class boundaries.
        Falls back to fixed-line chunks if AST parsing fails.
        """
        rel = str(filepath.relative_to(repo_root))
        lines = src.splitlines()
        chunks = []

        try:
            tree = ast.parse(src)
        except SyntaxError:
            # Fallback: fixed-line chunks
            return self._fixed_chunks(lines, rel)

        seen_ranges: set[tuple[int, int]] = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                continue
            if not (hasattr(node, "lineno") and hasattr(node, "end_lineno")):
                continue

            start = node.lineno - 1          # 0-indexed
            end   = node.end_lineno          # exclusive

            # Skip duplicate ranges (nested defs already covered by parent)
            key = (start, end)
            if key in seen_ranges:
                continue
            seen_ranges.add(key)

            text = "\n".join(lines[start:end]).strip()
            if not text or len(text) > MAX_CHUNK_LEN:
                continue

            chunks.append({
                "text":  text,
                "file":  rel,
                "name":  node.name,
                "lines": f"{node.lineno}-{node.end_lineno}",
            })

        # If AST found nothing (e.g. file is all top-level statements)
        if not chunks:
            return self._fixed_chunks(lines, rel)

        return chunks

    def _fixed_chunks(self, lines: list[str], rel_path: str) -> list[dict]:
        """Fallback: split into fixed-size line windows."""
        chunks = []
        for i in range(0, len(lines), FALLBACK_LINES):
            text = "\n".join(lines[i : i + FALLBACK_LINES]).strip()
            if text and len(text) <= MAX_CHUNK_LEN:
                chunks.append({
                    "text":  text,
                    "file":  rel_path,
                    "name":  f"lines_{i+1}_{i+FALLBACK_LINES}",
                    "lines": f"{i+1}-{i+FALLBACK_LINES}",
                })
        return chunks

    # ── Embed + Store ─────────────────────────────────────────────────────────

    def _load_model(self):
        """Load the sentence-transformer model (cached after first load)."""
        if self.model is None:
            self.model = SentenceTransformer(EMBED_MODEL)

    def _store(self, chunks: list[dict]):
        """Embed all chunks and upsert into ChromaDB."""
        os.makedirs(CHROMA_DIR, exist_ok=True)
        client = chromadb.PersistentClient(path=CHROMA_DIR)

        # Fresh collection each index run
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
        self.collection = client.create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

        texts = [c["text"] for c in chunks]

        # Batch embed — efficient on CPU
        print(f"[ASDA] Embedding {len(texts)} chunks (this may take ~30s)...")
        vectors = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        # Upsert in batches of 500 (ChromaDB limit)
        batch_size = 500
        for i in range(0, len(chunks), batch_size):
            batch     = chunks[i : i + batch_size]
            batch_vec = vectors[i : i + batch_size]
            self.collection.upsert(
                ids=[
                    f"{c['file']}::{c['name']}::{j}"
                    for j, c in enumerate(batch, start=i)
                ],
                embeddings=[v.tolist() for v in batch_vec],
                documents=[c["text"] for c in batch],
                metadatas=[{
                    "file":  c["file"],
                    "name":  c["name"],
                    "lines": c["lines"],
                } for c in batch],
            )