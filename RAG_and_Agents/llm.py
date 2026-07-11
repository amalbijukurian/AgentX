"""
ASDA v1 — LLM Layer
====================
Handles three jobs:
  1. Build a structured prompt from RAG chunks + user task
  2. Call the OpenAI API (GPT-4o)
  3. Parse the response into structured data the agent can act on

Usage:
    from llm import LLMLayer
    llm = LLMLayer()
    result = llm.analyse(chunks, task, repo_path)
    # result → { diagnosis, files: [{path, original, new_code}], summary }
"""

import os
import json
import difflib
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

# Explicit path — a bare load_dotenv() resolves against the cwd, which breaks
# when the backend is launched from backend/ instead of this folder.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


# ── Constants ────────────────────────────────────────────────────────────────

MODEL          = "openai/gpt-oss-120b"
MAX_TOKENS     = 4096
TEMPERATURE    = 0.2      # low = more deterministic code output
MAX_RETRIES    = 3        # max fix attempts on test failure
MAX_CHUNK_CHARS = 1500    # truncate very long chunks in the prompt


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ASDA — an Autonomous Software Development Agent.

You are given:
- A user task (bug fix, feature request, refactor, or improvement)
- Relevant code chunks retrieved from the codebase (file path, function name, source)

Your job:
1. DIAGNOSE — identify all bugs, issues, or improvements needed for the task
2. FIX — generate the corrected/improved version of each affected file
3. EXPLAIN — write a clear PR description summarising what changed and why

CRITICAL RULES:
- Only modify files that are genuinely relevant to the task
- Preserve the existing code style, naming conventions, and patterns
- Never remove existing functionality unless the task explicitly asks
- Always include complete file content in your response — not just the changed lines
- If a file does not need changes, do not include it in your response

RESPONSE FORMAT:
You must respond with valid JSON only. No markdown, no explanation outside the JSON.

{
  "diagnosis": "Clear explanation of what was wrong or what needs to change",
  "files": [
    {
      "path": "relative/path/to/file.py",
      "new_code": "complete new file content here"
    }
  ],
  "pr_title": "Short PR title (under 72 chars)",
  "pr_body": "Detailed PR description — what changed, why, and what was tested"
}
"""

RETRY_SYSTEM_PROMPT = """You are ASDA — an Autonomous Software Development Agent.

Your previous code change caused test failures. Your job is to fix the code so all tests pass.

You will be given:
- The original task
- The code you previously generated
- The test failure output

Analyse the test failure carefully and generate a corrected version.

RESPONSE FORMAT — valid JSON only, no markdown:
{
  "diagnosis": "What caused the test failure and how you fixed it",
  "files": [
    {
      "path": "relative/path/to/file.py",
      "new_code": "complete corrected file content"
    }
  ],
  "pr_title": "Short PR title",
  "pr_body": "Updated PR description"
}
"""


ASK_SYSTEM_PROMPT = """You are ASDA — an Autonomous Software Development Agent in Q&A mode.

You are given:
- A question about a codebase
- Relevant code chunks retrieved from that codebase (file path, function name, source)

Your job is to answer the question clearly and accurately based on the code provided.

RULES:
- Answer only from what you can see in the retrieved code chunks
- If the answer is not in the provided chunks, say so clearly
- Reference specific file paths and function names in your answer
- Keep answers concise but complete
- If the question is about what the repo does, summarise based on the code structure you can see
- Never make up code or functionality that is not in the chunks

RESPONSE FORMAT — valid JSON only, no markdown:
{
  "answer": "Your detailed answer to the question",
  "references": [
    {
      "file": "path/to/file",
      "name": "function_or_class_name",
      "relevance": "why this chunk is relevant to the answer"
    }
  ],
  "confidence": "high | medium | low",
  "note": "Any caveats — e.g. if the answer is partial because relevant code was not retrieved"
}
"""


# ── LLM Layer ─────────────────────────────────────────────────────────────────

class LLMLayer:
    """
    Wraps OpenAI GPT-4o for code analysis and generation.

    Public methods
    --------------
    analyse(chunks, task, repo_path)    [edit mode]
        → { diagnosis, files, pr_title, pr_body }

    answer(chunks, question)            [ask mode]
        → { answer, references, confidence, note }

    retry(task, previous_result, test_output)
        → { diagnosis, files, pr_title, pr_body }
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not found. "
                "Add it to your .env file."
            )
        self.client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    # ── Public API ────────────────────────────────────────────────────────────

    def analyse(
        self,
        chunks: list[dict],
        task: str,
        repo_path: Optional[str] = None,
    ) -> dict:
        """
        Analyse retrieved chunks and generate fixes for the given task.

        Parameters
        ----------
        chunks    : top-k chunks from rag.retrieve()
        task      : user's natural language task
        repo_path : optional — used to read full file content for context

        Returns
        -------
        {
            diagnosis : str,
            files     : [{ path, new_code, original }],
            pr_title  : str,
            pr_body   : str,
        }
        """
        print(f"\n[ASDA/LLM] Analysing task: {task}")
        print(f"[ASDA/LLM] Context: {len(chunks)} chunks loaded")

        prompt = self._build_prompt(chunks, task, repo_path)
        raw    = self._call_openai(SYSTEM_PROMPT, prompt)
        result = self._parse_response(raw)

        # Attach original file content to each file entry for diffing
        if repo_path:
            result = self._attach_originals(result, repo_path)

        print(f"[ASDA/LLM] Diagnosis complete — "
              f"{len(result.get('files', []))} file(s) to change")

        return result

    def answer(
        self,
        chunks: list[dict],
        question: str,
    ) -> dict:
        """
        Answer a natural language question about the codebase.

        Parameters
        ----------
        chunks   : top-k chunks from rag.retrieve()
        question : user's natural language question

        Returns
        -------
        {
            answer     : str,
            references : [{ file, name, relevance }],
            confidence : "high" | "medium" | "low",
            note       : str,
        }
        """
        print(f"\n[ASDA/LLM] Answering question: {question}")
        print(f"[ASDA/LLM] Context: {len(chunks)} chunks loaded")

        prompt = self._build_ask_prompt(chunks, question)
        raw    = self._call_openai(ASK_SYSTEM_PROMPT, prompt)
        result = self._parse_ask_response(raw)

        print(f"[ASDA/LLM] Answer ready (confidence: {result.get('confidence', '?')})")
        return result

    def show_answer(self, result: dict):
        """Pretty-print the Q&A answer to the terminal."""
        print("\n" + "─" * 55)
        print("  ASDA ANSWER")
        print("─" * 55)
        print(result.get("answer", "No answer provided."))

        refs = result.get("references", [])
        if refs:
            print(f"\n  References ({len(refs)}):")
            for r in refs:
                print(f"  → {r.get('file')} :: {r.get('name')}")
                print(f"    {r.get('relevance', '')}")

        confidence = result.get("confidence", "")
        note       = result.get("note", "")
        if confidence:
            print(f"\n  Confidence: {confidence}")
        if note:
            print(f"  Note: {note}")
        print("─" * 55)

    def retry(
        self,
        task: str,
        previous_result: dict,
        test_output: str,
        attempt: int = 1,
    ) -> dict:
        """
        Re-prompt the LLM after test failures.

        Parameters
        ----------
        task            : original user task
        previous_result : the result dict from the previous analyse() call
        test_output     : pytest stdout/stderr from the failed run
        attempt         : retry number (shown in logs)

        Returns
        -------
        Same structure as analyse()
        """
        print(f"\n[ASDA/LLM] Retry {attempt}/{MAX_RETRIES} — "
              f"fixing test failures...")

        prompt = self._build_retry_prompt(task, previous_result, test_output)
        raw    = self._call_openai(RETRY_SYSTEM_PROMPT, prompt)
        result = self._parse_response(raw)

        # Preserve originals from the previous result for diffing
        originals = {
            f["path"]: f.get("original", "")
            for f in previous_result.get("files", [])
        }
        for f in result.get("files", []):
            f["original"] = originals.get(f["path"], "")

        print(f"[ASDA/LLM] Retry {attempt} complete — "
              f"{len(result.get('files', []))} file(s) updated")

        return result

    def show_diagnosis(self, result: dict):
        """Pretty-print the diagnosis to the terminal."""
        print("\n" + "─" * 55)
        print("  ASDA DIAGNOSIS")
        print("─" * 55)
        print(result.get("diagnosis", "No diagnosis provided."))
        print(f"\n  Files to change: {len(result.get('files', []))}")
        for f in result.get("files", []):
            print(f"  → {f['path']}")
        print("─" * 55)

    def show_diff(self, result: dict) -> bool:
        """
        Show a unified diff for each file and ask for confirmation.

        Returns True if developer confirms, False if they abort.
        """
        files = result.get("files", [])
        if not files:
            print("[ASDA/LLM] No file changes to show.")
            return False

        print("\n" + "─" * 55)
        print("  PROPOSED CHANGES")
        print("─" * 55)

        for f in files:
            path      = f.get("path", "unknown")
            original  = f.get("original", "")
            new_code  = f.get("new_code", "")

            diff = list(difflib.unified_diff(
                original.splitlines(keepends=True),
                new_code.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            ))

            print(f"\n  File: {path}")
            if diff:
                for line in diff[:80]:   # cap at 80 lines for readability
                    print(f"  {line}")
                if len(diff) > 80:
                    print(f"  ... ({len(diff) - 80} more lines)")
            else:
                print("  (no changes detected)")

        print("\n" + "─" * 55)
        confirm = input("  Confirm changes? (y/n): ").strip().lower()
        return confirm == "y"

    # ── Prompt builders ───────────────────────────────────────────────────────

    def _build_prompt(
        self,
        chunks: list[dict],
        task: str,
        repo_path: Optional[str],
    ) -> str:
        """Build the user message for the initial analysis call."""
        lines = []

        lines.append(f"TASK:\n{task}\n")

        lines.append("RETRIEVED CODE CONTEXT:")
        lines.append("(These are the most relevant functions/classes from the codebase)\n")

        for i, chunk in enumerate(chunks, 1):
            header = (
                f"[{i}] File: {chunk['file']} "
                f"| Function/Class: {chunk['name']} "
                f"| Lines: {chunk['lines']} "
                f"| Relevance: {chunk.get('score', '?')}"
            )
            lines.append(header)
            lines.append("-" * len(header))

            text = chunk["text"]
            if len(text) > MAX_CHUNK_CHARS:
                text = text[:MAX_CHUNK_CHARS] + "\n... (truncated)"

            lines.append(text)
            lines.append("")

        lines.append(
            "INSTRUCTIONS:\n"
            "Analyse the code above in the context of the task. "
            "Generate the complete corrected file(s). "
            "Respond in JSON format as specified."
        )

        return "\n".join(lines)

    def _build_retry_prompt(
        self,
        task: str,
        previous_result: dict,
        test_output: str,
    ) -> str:
        """Build the prompt for a retry after test failure."""
        lines = []

        lines.append(f"ORIGINAL TASK:\n{task}\n")

        lines.append("YOUR PREVIOUS CODE CHANGES:")
        for f in previous_result.get("files", []):
            lines.append(f"\nFile: {f['path']}")
            lines.append("-" * 40)
            code = f.get("new_code", "")
            if len(code) > MAX_CHUNK_CHARS * 2:
                code = code[:MAX_CHUNK_CHARS * 2] + "\n... (truncated)"
            lines.append(code)

        lines.append(f"\nTEST FAILURE OUTPUT:\n{test_output[:3000]}")

        lines.append(
            "\nINSTRUCTIONS:\n"
            "Fix the code so all tests pass. "
            "Respond in JSON format as specified."
        )

        return "\n".join(lines)

    # ── OpenAI call ───────────────────────────────────────────────────────────

    def _call_openai(self, system: str, user: str) -> str:
        """Make the OpenAI API call and return raw response text."""
        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
            )
            return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}")

    # ── Response parser ───────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> dict:
        """
        Parse the LLM's JSON response into a structured dict.
        Handles malformed JSON gracefully.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try stripping markdown fences if the model added them
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
            if cleaned.endswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[:-1])
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"LLM returned invalid JSON.\n"
                    f"Parse error: {e}\n"
                    f"Raw response (first 500 chars):\n{raw[:500]}"
                )

        # Validate required keys
        required = {"diagnosis", "files", "pr_title", "pr_body"}
        missing  = required - set(data.keys())
        if missing:
            raise ValueError(
                f"LLM response missing required keys: {missing}\n"
                f"Got: {list(data.keys())}"
            )

        # Validate files list
        for i, f in enumerate(data.get("files", [])):
            if "path" not in f or "new_code" not in f:
                raise ValueError(
                    f"File entry {i} missing 'path' or 'new_code'.\n"
                    f"Got: {list(f.keys())}"
                )

        return data

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _attach_originals(self, result: dict, repo_path: str) -> dict:
        """
        Read the original file content from disk for each file in the result.
        Attaches as 'original' key — used for diffing and backup.
        """
        import os
        for f in result.get("files", []):
            full_path = os.path.join(repo_path, f["path"])
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    f["original"] = fh.read()
            except FileNotFoundError:
                f["original"] = ""   # new file — no original

        return result

    def _build_ask_prompt(self, chunks: list[dict], question: str) -> str:
        """Build the user message for the Q&A call."""
        lines = []
        lines.append(f"QUESTION:\n{question}\n")
        lines.append("RETRIEVED CODE CONTEXT:")
        lines.append("(Most relevant code chunks from the codebase)\n")

        for i, chunk in enumerate(chunks, 1):
            header = (
                f"[{i}] File: {chunk['file']} "
                f"| Function/Class: {chunk['name']} "
                f"| Lines: {chunk['lines']} "
                f"| Relevance score: {chunk.get('score', '?')}"
            )
            lines.append(header)
            lines.append("-" * len(header))

            text = chunk["text"]
            if len(text) > MAX_CHUNK_CHARS:
                text = text[:MAX_CHUNK_CHARS] + "\n... (truncated)"

            lines.append(text)
            lines.append("")

        lines.append(
            "INSTRUCTIONS:\n"
            "Answer the question based on the code above. "
            "Be specific — reference file names and function names. "
            "Respond in JSON format as specified."
        )

        return "\n".join(lines)

    def _parse_ask_response(self, raw: str) -> dict:
        """Parse the Q&A JSON response."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
            if cleaned.endswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[:-1])
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"LLM returned invalid JSON.\n"
                    f"Parse error: {e}\n"
                    f"Raw response:\n{raw[:500]}"
                )

        # Ensure required keys exist with defaults
        data.setdefault("answer",     "No answer provided.")
        data.setdefault("references", [])
        data.setdefault("confidence", "low")
        data.setdefault("note",       "")

        return data