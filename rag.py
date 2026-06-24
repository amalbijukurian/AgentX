"""
ASDA v1 — RAG Pipeline
======================
Phase 1: Clone → Walk → Universal AST Chunk → Embed → Store → Retrieve

Chunking strategy:
  - All languages: tree-sitter universal AST parser
  - Extracts functions, methods, classes by language-specific node types
  - Falls back to fixed-line chunks if tree-sitter fails or lang unsupported

Usage:
    from rag import RAGPipeline
    rag = RAGPipeline()
    rag.index(repo_url, github_token)
    chunks = rag.retrieve("fix the divide by zero bug in utils")
"""

import os
import ast
import re
import shutil
import hashlib
import tempfile
import subprocess
import atexit
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer


# ── Constants ────────────────────────────────────────────────────────────────

EMBED_MODEL    = "all-MiniLM-L6-v2"
CHROMA_DIR     = ".asda/chroma"
REPO_CACHE_DIR = ".asda/repos"    # persistent repo cache between runs
COLLECTION     = "codebase"
TOP_K          = 6
MAX_CHUNK_LEN  = 6000
FALLBACK_LINES = 60

SKIP_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "env",
    "node_modules", "dist", "build", ".mypy_cache",
    ".pytest_cache", "migrations", ".asda",
}

SKIP_FILES = {"setup.py", "conf.py"}

# ── Language map ─────────────────────────────────────────────────────────────
# Maps file extension → (tree-sitter language name, function node types)
# node types are the tree-sitter node type names for function/class definitions

LANG_MAP = {
    ".py":   ("python",     ["function_definition", "async_function_definition", "class_definition"]),
    ".js":   ("javascript", ["function_declaration", "function_expression", "arrow_function", "class_declaration", "method_definition"]),
    ".jsx":  ("javascript", ["function_declaration", "function_expression", "arrow_function", "class_declaration", "method_definition"]),
    ".ts":   ("typescript", ["function_declaration", "function_expression", "arrow_function", "class_declaration", "method_definition"]),
    ".tsx":  ("tsx",        ["function_declaration", "function_expression", "arrow_function", "class_declaration", "method_definition"]),
    ".java": ("java",       ["method_declaration", "class_declaration", "constructor_declaration"]),
    ".go":   ("go",         ["function_declaration", "method_declaration", "type_declaration"]),
    ".rb":   ("ruby",       ["method", "singleton_method", "class", "module"]),
    ".rs":   ("rust",       ["function_item", "impl_item", "struct_item", "enum_item"]),
    ".cpp":  ("cpp",        ["function_definition", "class_specifier"]),
    ".c":    ("c",          ["function_definition"]),
    ".h":    ("c",          ["function_definition"]),
}

SUPPORTED_EXTENSIONS = set(LANG_MAP.keys())


# ── Tree-sitter loader ────────────────────────────────────────────────────────

def _load_treesitter():
    """
    Try to import tree-sitter-language-pack.
    Returns (get_parser, True) if available, (None, False) if not installed.
    """
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser, True
    except ImportError:
        return None, False


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
        self.model          : Optional[SentenceTransformer] = None
        self.collection     : Optional[chromadb.Collection] = None
        self.repo_path      : Optional[Path] = None
        self._loaded        = False
        self._temp_dirs     : list[Path] = []   # track temp dirs for cleanup
        self._ts_get_parser, self._ts_available = _load_treesitter()

        if self._ts_available:
            print("[ASDA] tree-sitter available — universal AST chunking enabled")
        else:
            print("[ASDA] tree-sitter not found — using fixed-line chunker")
            print("[ASDA] To enable universal AST: pip install tree-sitter tree-sitter-language-pack")

        # Register cleanup on exit
        atexit.register(self.cleanup)

    # ── Public API ────────────────────────────────────────────────────────────

    def index(self, repo_url: str, github_token: str) -> dict:
        """
        Clone (or pull) `repo_url` and build a ChromaDB index of the codebase.

        Clone strategy:
          - First run  : clone into .asda/repos/<repo-slug>/
          - Repeat run : git pull to update — no re-clone, no temp folder
          - Temp dirs  : cleaned up on exit via atexit

        Returns a summary dict:
            { files, chunks, skipped, repo_path }
        """
        print("\n[ASDA] Loading embedding model...")
        self._load_model()

        self.repo_path = self._clone_or_pull(repo_url, github_token)
        print(f"[ASDA] Repo at {self.repo_path}")

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

    def cleanup(self):
        """
        Remove any temp dirs created this session.
        Called automatically on exit via atexit.
        """
        for path in self._temp_dirs:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        self._temp_dirs.clear()

    def retrieve(self, task: str, k: int = TOP_K) -> list[dict]:
        """
        Embed `task` and return the top-k most relevant code chunks.

        Each chunk: { text, file, name, lines, score }
        """
        if not self._loaded:
            raise RuntimeError("Index not built. Call .index(repo_url, token) first.")

        if self.collection.count() == 0:
            print("[ASDA] Index is empty — no supported source files found in this repo.")
            return []

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
                "score": round(1 - dist, 4),
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

    # ── Clone / Pull ──────────────────────────────────────────────────────────

    def _clone_or_pull(self, repo_url: str, token: str) -> Path:
        """
        Smart clone strategy:
          - Derives a stable cache folder from the repo URL
          - If cache folder exists: git pull (fast, no re-download)
          - If not: git clone --depth=1 into the cache folder
          - Cache lives in .asda/repos/ — persists between runs
          - No temp folders piling up in system temp
        """
        # Derive a stable folder name from the repo URL
        clean_url = re.sub(r"https?://[^@]+@", "https://", repo_url)
        slug      = re.sub(r"[^a-zA-Z0-9_-]", "_", clean_url.rstrip("/").split("/")[-1].replace(".git", ""))
        url_hash  = hashlib.md5(clean_url.encode()).hexdigest()[:8]
        cache_dir = Path(REPO_CACHE_DIR) / f"{slug}_{url_hash}"

        # Build auth URL
        auth_url = repo_url
        if token and "github.com" in repo_url:
            auth_url = repo_url.replace("https://", f"https://{token}@")
            if not auth_url.endswith(".git"):
                auth_url += ".git"

        if cache_dir.exists() and (cache_dir / ".git").exists():
            # ── Repo already cached — just pull latest ────────────────────────
            print(f"[ASDA] Repo cached — pulling latest changes...")
            result = subprocess.run(
                ["git", "-C", str(cache_dir), "pull", "--depth=1", "origin"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                # Pull failed (e.g. shallow repo conflict) — re-clone fresh
                print(f"[ASDA] Pull failed, re-cloning...")
                shutil.rmtree(cache_dir, ignore_errors=True)
                self._do_clone(auth_url, cache_dir)
            else:
                print(f"[ASDA] Repo updated.")
        else:
            # ── First time — clone into cache folder ──────────────────────────
            print(f"[ASDA] Cloning repository...")
            cache_dir.parent.mkdir(parents=True, exist_ok=True)
            self._do_clone(auth_url, cache_dir)

        return cache_dir

    def _do_clone(self, auth_url: str, dest: Path) -> None:
        """Run git clone --depth=1 into dest. Raises on failure."""
        result = subprocess.run(
            ["git", "clone", "--depth=1", auth_url, str(dest)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"Git clone failed:\n{result.stderr.strip()}")

    # ── Walk ──────────────────────────────────────────────────────────────────

    def _build_chunks(self, repo_path: Path) -> tuple[list[dict], dict]:
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
        """Yield supported source files, skipping irrelevant directories."""
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_EXTENSIONS and fname not in SKIP_FILES:
                    yield Path(dirpath) / fname

    # ── Chunker ───────────────────────────────────────────────────────────────

    def _chunk_file(self, filepath: Path, src: str, repo_root: Path) -> list[dict]:
        """
        Chunk a source file into semantically complete units.

        Priority:
          1. tree-sitter universal AST (if installed)
          2. Python built-in ast module (Python files only, if tree-sitter missing)
          3. Fixed-line fallback (always available)
        """
        rel   = str(filepath.relative_to(repo_root))
        ext   = filepath.suffix.lower()
        lines = src.splitlines()

        # ── Strategy 1: tree-sitter (universal, all languages) ────────────────
        if self._ts_available and ext in LANG_MAP:
            chunks = self._treesitter_chunks(src, lines, rel, ext)
            if chunks:
                return chunks

        # ── Strategy 2: Python built-in ast (Python only, tree-sitter missing) ─
        if ext == ".py":
            chunks = self._python_ast_chunks(src, lines, rel)
            if chunks:
                return chunks

        # ── Strategy 3: Fixed-line fallback ───────────────────────────────────
        return self._fixed_chunks(lines, rel)

    def _treesitter_chunks(
        self, src: str, lines: list[str], rel: str, ext: str
    ) -> list[dict]:
        """
        Use tree-sitter to extract function/class chunks for any language.
        Returns empty list if parsing fails — caller falls back to next strategy.
        """
        lang_name, node_types = LANG_MAP[ext]

        try:
            parser = self._ts_get_parser(lang_name)
        except Exception:
            return []   # language not available in this tree-sitter build

        try:
            tree = parser.parse(src.encode("utf-8"))
        except Exception:
            return []

        chunks        = []
        seen_ranges   = set()

        def walk(node):
            """Recursively walk tree-sitter nodes."""
            if node.type in node_types:
                start_line = node.start_point[0]   # 0-indexed
                end_line   = node.end_point[0] + 1  # exclusive

                key = (start_line, end_line)
                if key not in seen_ranges:
                    seen_ranges.add(key)

                    text = "\n".join(lines[start_line:end_line]).strip()

                    if text and len(text) <= MAX_CHUNK_LEN:
                        # Extract name: first named child is usually the identifier
                        name = self._extract_name(node, rel, start_line)

                        chunks.append({
                            "text":  text,
                            "file":  rel,
                            "name":  name,
                            "lines": f"{start_line + 1}-{end_line}",
                        })

            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return chunks

    def _extract_name(self, node, rel: str, start_line: int) -> str:
        """
        Extract a human-readable name from a tree-sitter node.
        Looks for the first 'identifier' or 'name' child node.
        Falls back to node type + line number.
        """
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                return child.text.decode("utf-8") if child.text else child.type
        return f"{node.type}_line{start_line + 1}"

    def _python_ast_chunks(self, src: str, lines: list[str], rel: str) -> list[dict]:
        """
        Python built-in AST chunker — used when tree-sitter is not installed.
        Only works for .py files.
        """
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return []

        chunks      = []
        seen_ranges = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if not (hasattr(node, "lineno") and hasattr(node, "end_lineno")):
                continue

            start = node.lineno - 1
            end   = node.end_lineno
            key   = (start, end)

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

        return chunks

    def _fixed_chunks(self, lines: list[str], rel_path: str) -> list[dict]:
        """Last-resort fallback: fixed-size line windows."""
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
        if self.model is None:
            self.model = SentenceTransformer(EMBED_MODEL)

    def _store(self, chunks: list[dict]):
        """Embed all chunks and upsert into ChromaDB."""
        os.makedirs(CHROMA_DIR, exist_ok=True)
        client = chromadb.PersistentClient(path=CHROMA_DIR)

        if not chunks:
            print("[ASDA] Warning: no chunks to index.")
            print(f"[ASDA] Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
            self.collection = client.get_or_create_collection(name=COLLECTION)
            self._loaded = True
            return

        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass

        self.collection = client.create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

        texts = [c["text"] for c in chunks]

        print(f"[ASDA] Embedding {len(texts)} chunks (this may take ~30s)...")
        vectors = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

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