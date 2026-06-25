"""
ASDA v1 — LLM Layer Smoke Test
================================
Tests llm.py independently — no RAG needed.
Sends a fake chunk + task to the LLM and prints the result.

Usage:
    python test_llm.py
"""

from RAG_and_Agents.llm import LLMLayer


# ── Fake chunk (simulates what rag.retrieve() returns) ────────────────────────

FAKE_CHUNKS = [
    {
        "text": """def divide(a, b):
    \"\"\"Divide a by b and return the result.\"\"\"
    return a / b""",
        "file":  "utils/math.py",
        "name":  "divide",
        "lines": "1-3",
        "score": 0.91,
    },
    {
        "text": """def calculate_average(numbers):
    \"\"\"Return the average of a list of numbers.\"\"\"
    total = sum(numbers)
    return divide(total, len(numbers))""",
        "file":  "utils/math.py",
        "name":  "calculate_average",
        "lines": "6-10",
        "score": 0.78,
    },
]

FAKE_TASK = "fix the divide by zero error in utils/math.py and add proper error handling"


def main():
    print("=" * 55)
    print("  ASDA v1 — LLM Layer Test")
    print("=" * 55)

    llm = LLMLayer()

    # ── Run analysis ──────────────────────────────────────────────────────────
    result = llm.analyse(FAKE_CHUNKS, FAKE_TASK)

    # ── Show diagnosis ────────────────────────────────────────────────────────
    llm.show_diagnosis(result)

    # ── Show raw result ───────────────────────────────────────────────────────
    print("\n── Raw result keys ────────────────────────────────")
    print(f"  diagnosis : {result['diagnosis'][:120]}...")
    print(f"  pr_title  : {result['pr_title']}")
    print(f"  files     : {[f['path'] for f in result['files']]}")
    print(f"  pr_body   : {result['pr_body'][:120]}...")

    # ── Show generated code ───────────────────────────────────────────────────
    print("\n── Generated code ─────────────────────────────────")
    for f in result["files"]:
        print(f"\n  File: {f['path']}")
        print("  " + "-" * 40)
        for line in f["new_code"].splitlines():
            print(f"  {line}")

    # ── Show diff (no repo_path so original will be empty) ────────────────────
    print("\n── Diff preview ───────────────────────────────────")
    print("  (original will be empty since no repo is cloned in this test)")
    confirmed = llm.show_diff(result)
    print(f"\n  Developer confirmed: {confirmed}")

    print("\n── Phase 2 LLM layer is working ───────────────────\n")


if __name__ == "__main__":
    main()