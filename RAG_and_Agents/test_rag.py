"""
ASDA v1 — RAG Pipeline Smoke Test
===================================
Run this to verify Phase 1 is working end-to-end.

Usage:
    python test_rag.py

You will be prompted for:
    - GitHub repo URL  (any public Python repo works)
    - GitHub PAT       (needed for cloning; fine-grained or classic)
"""

from RAG_and_Agents.rag import RAGPipeline


def main():
    print("=" * 55)
    print("  ASDA v1 — RAG Pipeline Test")
    print("=" * 55)

    repo_url = input("\nGitHub repo URL: ").strip()
    token    = input("GitHub PAT (press Enter to skip for public repos): ").strip()

    rag = RAGPipeline()

    # ── Index ────────────────────────────────────────────────────────────────
    stats = rag.index(repo_url, token)

    print("\n── Index Summary ──────────────────────────────")
    print(f"  Files indexed : {stats['files']}")
    print(f"  Chunks stored : {stats['chunks']}")
    print(f"  Files skipped : {stats['skipped']}")
    print(f"  Repo path     : {stats['repo_path']}")

    # ── Retrieve ─────────────────────────────────────────────────────────────
    print("\n── Retrieval Test ─────────────────────────────")
    task = input("\nDescribe a task or bug (natural language): ").strip()

    chunks = rag.retrieve(task, k=5)

    print(f"\nTop {len(chunks)} chunks retrieved:\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}] {chunk['file']} :: {chunk['name']} "
              f"(lines {chunk['lines']}) — score {chunk['score']}")
        print(f"      {chunk['text'][:120].replace(chr(10), ' ')}...")
        print()

    print("── Phase 1 complete. RAG pipeline is working. ──\n")


if __name__ == "__main__":
    main()