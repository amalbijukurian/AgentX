"""
test_tools.py
-------------
Tool for running the test suite of the cloned repository.
The LLM uses this to verify its fixes didn't break anything.
If tests fail, it reads the error output and tries to fix again.
"""

import subprocess
import os


def run_tests(repo_path: str) -> dict:
    """
    Run the pytest test suite inside the given repository.

    Args:
        repo_path: Root directory of the cloned repo.
                   Example: "/tmp/cloned_repo"

    Returns:
        A dictionary with:
            - passed (bool): True if all tests passed
            - output (str): Full output from pytest (what you'd see in terminal)
            - summary (str): Just the last line (e.g. "3 passed, 1 failed")
    """

    # Check repo exists
    if not os.path.exists(repo_path):
        return {
            "passed": False,
            "output": f"ERROR: Repo path not found — {repo_path}",
            "summary": "Could not run tests"
        }

    # Check pytest is available
    # --tb=short means show short tracebacks (not full, not nothing)
    # -v means verbose (show each test name)
    command = ["python", "-m", "pytest", "--tb=short", "-v"]

    try:
        result = subprocess.run(
            command,
            cwd=repo_path,          # Run FROM inside the repo folder
            capture_output=True,    # Capture stdout and stderr
            text=True,              # Return as string, not bytes
            timeout=120             # Stop after 2 minutes (safety limit)
        )

        # Combine stdout and stderr into one output string
        full_output = result.stdout + result.stderr

        # Extract the summary line (last non-empty line of output)
        lines = [line for line in full_output.strip().split("\n") if line.strip()]
        summary = lines[-1] if lines else "No output from pytest"

        # returncode 0 = all tests passed
        # returncode 1 = some tests failed
        # returncode 5 = no tests found (still "ok" for our purposes)
        passed = result.returncode in [0, 5]

        return {
            "passed": passed,
            "output": full_output,
            "summary": summary
        }

    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "output": "ERROR: Tests timed out after 120 seconds",
            "summary": "Timeout"
        }

    except FileNotFoundError:
        return {
            "passed": False,
            "output": "ERROR: Python or pytest not found. Is pytest installed?",
            "summary": "pytest not found"
        }

    except Exception as e:
        return {
            "passed": False,
            "output": f"ERROR running tests: {str(e)}",
            "summary": "Error"
        }


def format_test_result(result: dict) -> str:
    """
    Convert the test result dictionary into a readable string
    that can be returned to the LLM.

    Args:
        result: The dict returned by run_tests()

    Returns:
        A formatted string the LLM can read and reason about.
    """
    status = "PASSED" if result["passed"] else "FAILED"

    return f"""
Test Result: {status}
Summary: {result["summary"]}

Full Output:
{result["output"]}
""".strip()