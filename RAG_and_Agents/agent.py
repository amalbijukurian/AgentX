"""
ASDA v1 — Agent Orchestrator
==============================
Connects the full pipeline:
  rag.py → llm.py → tools.py → GitHub PR

Usage (CLI):
    python agent.py --repo https://github.com/owner/repo --task "fix the bug in auth.py"

Usage (from api.py):
    from agent import Agent
    agent = Agent()
    result = agent.run(repo_url, token, task)
"""

import argparse
import os
import sys
from dotenv import load_dotenv

try:
    from RAG_and_Agents.rag import RAGPipeline
    from RAG_and_Agents.llm import LLMLayer
except ModuleNotFoundError as e:
    if e.name and e.name.split(".")[0] == "RAG_and_Agents":
        # Running standalone from inside RAG_and_Agents/ — use bare imports
        from rag import RAGPipeline
        from llm import LLMLayer
    else:
        # A real dependency is missing (e.g. chromadb) — don't mask it
        raise

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_RETRIES = 3   # max LLM retry attempts on test failure


# ── Agent ─────────────────────────────────────────────────────────────────────

class Agent:
    """
    ASDA v1 — Main orchestrator.

    Pipeline
    --------
    1. RAG  — clone repo, index codebase, retrieve relevant chunks
    2. LLM  — analyse chunks, generate fixes, show diff
    3. Tools — write files, run tests, commit, open PR

    Returns
    -------
    {
        success     : bool,
        diagnosis   : str,
        files       : [{ path, new_code, original }],
        test_result : { passed, output },
        pr_url      : str,
        error       : str   # only if success=False
    }
    """

    def __init__(self):
        self.rag   = RAGPipeline()
        self.llm   = LLMLayer()
        self.tools = None   # imported lazily — tools.py built by Member 2

    def run(self, repo_url: str, token: str, task: str, mode: str = "edit") -> dict:
        """
        Run the full ASDA pipeline for a given repo and task.
        """
        print("\n" + "=" * 55)
        print("  ASDA v1 — Autonomous Software Development Agent")
        print("=" * 55)
        print(f"  Repo : {repo_url}")
        print(f"  Task : {task}")
        print(f"  Mode : {mode}")
        print("=" * 55)

        try:
            # ── Phase 1: RAG ─────────────────────────────────────────────────
            stats  = self.rag.index(repo_url, token)
            chunks = self.rag.retrieve(task)

            if not chunks:
                return self._fail(
                    "No relevant code found in this repo for that task.\n"
                    "Possible reasons:\n"
                    "  1. Repo has no supported source files (.py .js .ts etc)\n"
                    "  2. Task is too vague — try describing a specific file or function\n"
                    "  3. For questions about the repo, use --mode ask"
                )

            print(f"\n[ASDA] Retrieved {len(chunks)} relevant chunks:")
            for c in chunks:
                print(f"  → {c['file']} :: {c['name']} "
                      f"(score: {c['score']})")

            # ── Phase 2: Route by mode ────────────────────────────────────────
            if mode == "ask":
                return self._run_ask(chunks, task)
            else:
                return self._run_edit(chunks, task, token, repo_url, stats)

        except Exception as e:
            print(f"\n[ASDA] Error: {e}")
            return self._fail(str(e))

    # ── Mode handlers ────────────────────────────────────────────────────────

    def _run_ask(self, chunks: list, question: str) -> dict:
        """Handle ask mode — answer a question about the codebase."""
        result = self.llm.answer(chunks, question)
        self.llm.show_answer(result)

        print("\n" + "=" * 55)
        print("  Done.")
        print("=" * 55 + "\n")

        return {
            "success"     : True,
            "mode"        : "ask",
            "answer"      : result.get("answer", ""),
            "references"  : result.get("references", []),
            "confidence"  : result.get("confidence", ""),
            "note"        : result.get("note", ""),
            "error"       : None,
        }

    def _run_edit(
        self,
        chunks: list,
        task: str,
        token: str,
        repo_url: str,
        stats: dict,
    ) -> dict:
        """Handle edit mode — analyse, fix, commit, PR."""
        result = self.llm.analyse(
            chunks    = chunks,
            task      = task,
            repo_path = stats["repo_path"],
        )

        self.llm.show_diagnosis(result)

        if not result.get("files"):
            return self._fail("LLM found no files to change for this task.")

        # Diff + confirm
        confirmed = self.llm.show_diff(result)
        if not confirmed:
            print("\n[ASDA] Aborted by developer. No files written.")
            return self._fail("Aborted by developer.", soft=True)

        # Write + test + git + PR
        tools = self._get_tools(stats["repo_path"])

        print("\n[ASDA] Writing files...")
        for f in result["files"]:
            tools.write_file(f["path"], f["new_code"])
            print(f"  ✓ {f['path']}")

        test_result = self._run_with_retry(tools, result, task, stats["repo_path"])

        if not test_result["passed"]:
            return self._fail(
                f"Tests failed after {MAX_RETRIES} attempts.\n"
                f"{test_result['output']}"
            )

        print("\n[ASDA] Tests passed ✓")

        branch  = self._branch_name(task)
        changed = [f["path"] for f in result["files"]]

        tools.git_branch(branch)
        tools.git_commit(changed, result["pr_title"])

        pr_url = tools.create_pr(
            token    = token,
            title    = result["pr_title"],
            body     = result["pr_body"],
            branch   = branch,
            repo_url = repo_url,
        )

        print(f"\n[ASDA] PR opened → {pr_url}")
        print("\n" + "=" * 55)
        print("  Done.")
        print("=" * 55 + "\n")

        return {
            "success"     : True,
            "mode"        : "edit",
            "diagnosis"   : result["diagnosis"],
            "files"       : result["files"],
            "test_result" : test_result,
            "pr_url"      : pr_url,
            "error"       : None,
        }

    # ── Retry loop ────────────────────────────────────────────────────────────

    def _run_with_retry(
        self,
        tools,
        result: dict,
        task: str,
        repo_path: str,
    ) -> dict:
        """
        Run tests. If they fail, re-prompt the LLM and retry.
        Returns the final test result dict.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"\n[ASDA] Running tests (attempt {attempt}/{MAX_RETRIES})...")
            test_result = tools.run_tests(repo_path)

            if test_result["passed"]:
                return test_result

            print(f"[ASDA] Tests failed on attempt {attempt}.")
            print(f"  {test_result['output'][:300]}...")

            if attempt == MAX_RETRIES:
                break

            # Re-prompt LLM with the failure output
            result = self.llm.retry(
                task            = task,
                previous_result = result,
                test_output     = test_result["output"],
                attempt         = attempt,
            )

            # Show new diff and confirm before writing again
            confirmed = self.llm.show_diff(result)
            if not confirmed:
                print("[ASDA] Retry aborted by developer.")
                return test_result

            print(f"\n[ASDA] Writing retry fixes...")
            for f in result["files"]:
                tools.write_file(f["path"], f["new_code"])
                print(f"  ✓ {f['path']}")

        return test_result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_tools(self, repo_path: str):
        """
        Lazy import of tools.py — built by Member 2.
        Falls back to a stub if tools.py isn't ready yet.
        """
        try:
            from RAG_and_Agents.tools import ToolLayer
        except ModuleNotFoundError as e:
            if not (e.name and e.name.split(".")[0] == "RAG_and_Agents"):
                raise  # real dependency missing inside tools.py — don't mask it
            try:
                from tools import ToolLayer
            except ModuleNotFoundError as e2:
                if e2.name != "tools":
                    raise
                print("[ASDA] Warning: tools.py not found — using stub.")
                return ToolStub(repo_path)
        return ToolLayer(repo_path)

    def _branch_name(self, task: str) -> str:
        """Generate a clean git branch name from the task string."""
        slug = task.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split()[:6])   # max 6 words
        return f"asda/{slug}"

    def _fail(self, message: str, soft: bool = False) -> dict:
        """Return a structured failure result."""
        if not soft:
            print(f"\n[ASDA] Failed: {message}")
        return {
            "success"     : False,
            "diagnosis"   : "",
            "files"       : [],
            "test_result" : {"passed": False, "output": ""},
            "pr_url"      : "",
            "error"       : message,
        }


# ── Tool Stub (used until Member 2 finishes tools.py) ─────────────────────────

class ToolStub:
    """
    Temporary stub for tools.py.
    Lets you test the full pipeline before Member 2 is done.
    Prints what it would do instead of actually doing it.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        print("[ASDA/Stub] ToolStub active — simulating tool calls.")

    def write_file(self, path: str, content: str):
        print(f"[ASDA/Stub] write_file({path}) — {len(content)} chars")

    def run_tests(self, repo_path: str) -> dict:
        print("[ASDA/Stub] run_tests() — returning mock PASSED")
        return {"passed": True, "output": "stub: all tests passed"}

    def git_branch(self, branch: str):
        print(f"[ASDA/Stub] git_branch({branch})")

    def git_commit(self, files: list, message: str):
        print(f"[ASDA/Stub] git_commit({files}, '{message}')")

    def create_pr(self, token, title, body, branch, repo_url) -> str:
        print(f"[ASDA/Stub] create_pr('{title}')")
        return "https://github.com/stub/repo/pull/1"


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ASDA v1 — Autonomous Software Development Agent"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository URL (e.g. https://github.com/owner/repo)"
    )
    parser.add_argument(
        "--task",
        required=True,
        help='Natural language task (e.g. "fix the divide by zero bug in utils.py")'
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub PAT (optional — will prompt if not provided)"
    )
    parser.add_argument(
        "--mode",
        choices=["ask", "edit"],
        default="edit",
        help=(
            "ask  — answer a question about the codebase (no code changes)\n"
            "edit — analyse, fix, and open a PR (default)"
        )
    )

    args = parser.parse_args()

    token = args.token or input("GitHub PAT (press Enter for public repos): ").strip()

    agent  = Agent()
    result = agent.run(
        repo_url = args.repo,
        token    = token,
        task     = args.task,
        mode     = args.mode,
    )

    if not result["success"]:
        print(f"\n[ASDA] Failed: {result['error']}")
        sys.exit(1)

    # Print mode-specific summary
    if result.get("mode") == "ask":
        print(f"\n[ASDA] Answer (confidence: {result.get('confidence', '?')})")
        print(result.get("answer", ""))
    else:
        print(f"\n[ASDA] PR → {result.get('pr_url', 'n/a')}")


if __name__ == "__main__":
    main()