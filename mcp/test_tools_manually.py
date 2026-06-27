"""
test_tools_manually.py
----------------------
Run this file to test every tool WITHOUT needing MCP running.
This is how you build and verify each tool one at a time.

Run with:
    python test_tools_manually.py

You should see PASS or FAIL for each test.
Fix any FAILs before moving on to running the full MCP server.
"""

import os
import tempfile
import shutil

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def test(name, condition, detail=""):
    if condition:
        print(f"  ✅ PASS — {name}")
    else:
        print(f"  ❌ FAIL — {name}")
        if detail:
            print(f"     Detail: {detail}")


# ─────────────────────────────────────────────────────────────
# TEST: file_tools
# ─────────────────────────────────────────────────────────────

def test_file_tools():
    print("\n── FILE TOOLS ──────────────────────────────────")

    from mcp.tools.file_tools import read_file, write_file, list_files, show_diff

    # Create a temp directory to work in
    tmpdir = tempfile.mkdtemp()
    test_file = os.path.join(tmpdir, "hello.py")

    try:
        # Test write_file
        result = write_file(test_file, "def hello():\n    return 'world'\n")
        test("write_file returns success", "SUCCESS" in result, result)
        test("write_file actually creates the file", os.path.exists(test_file))

        # Test read_file
        content = read_file(test_file)
        test("read_file returns file content", "def hello" in content, content[:100])
        test("read_file includes filename in output", "hello.py" in content)

        # Test read_file on missing file
        missing = read_file("/nonexistent/path/file.py")
        test("read_file handles missing file gracefully", "ERROR" in missing, missing)

        # Test list_files
        file_list = list_files(tmpdir, ".py")
        test("list_files finds .py files", "hello.py" in file_list, file_list)

        # Test show_diff
        original = "def hello():\n    return 'world'\n"
        modified = "def hello():\n    return 'hello world'\n"
        diff = show_diff(original, modified, "hello.py")
        test("show_diff shows changes", "world" in diff, diff[:200])
        test("show_diff shows + and - lines", "+" in diff and "-" in diff)

    finally:
        # Windows fix: .git folder has read-only files, need to force delete
        def force_remove(func, path, exc):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(tmpdir, onerror=force_remove)


# ─────────────────────────────────────────────────────────────
# TEST: test_tools
# ─────────────────────────────────────────────────────────────

def test_test_tools():
    print("\n── TEST TOOLS ──────────────────────────────────")

    from mcp.tools.test_tools import run_tests, format_test_result

    tmpdir = tempfile.mkdtemp()

    try:
        # Create a simple passing test
        test_file = os.path.join(tmpdir, "test_sample.py")
        with open(test_file, "w") as f:
            f.write("def test_always_passes():\n    assert 1 + 1 == 2\n")

        result = run_tests(tmpdir)
        test("run_tests returns a dict", isinstance(result, dict))
        test("run_tests dict has 'passed' key", "passed" in result)
        test("run_tests dict has 'output' key", "output" in result)
        test("run_tests dict has 'summary' key", "summary" in result)
        test("run_tests detects passing tests", result["passed"] is True, result["summary"])

        # Create a failing test
        fail_file = os.path.join(tmpdir, "test_fail.py")
        with open(fail_file, "w") as f:
            f.write("def test_always_fails():\n    assert 1 == 2\n")

        result_fail = run_tests(tmpdir)
        test("run_tests detects failing tests", result_fail["passed"] is False, result_fail["summary"])

        # Test formatter
        formatted = format_test_result(result)
        test("format_test_result returns string", isinstance(formatted, str))
        test("format_test_result contains PASSED/FAILED", "PASSED" in formatted or "FAILED" in formatted)

    finally:
        
        def force_remove(func, path, exc):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(tmpdir, onerror=force_remove)


# ─────────────────────────────────────────────────────────────
# TEST: git_tools (no network needed)
# ─────────────────────────────────────────────────────────────

def test_git_tools():
    print("\n── GIT TOOLS ───────────────────────────────────")

    import git
    import gc
    import time
    from mcp.tools.git_tools import create_branch, commit_changes, get_changed_files, get_current_branch

    tmpdir = tempfile.mkdtemp()
    repo = None  # track repo so we can close it before cleanup

    try:
        # Initialize a fresh git repo for testing
        repo = git.Repo.init(tmpdir)
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@test.com").release()

        # Create an initial commit so branches have a base
        init_file = os.path.join(tmpdir, "init.py")
        with open(init_file, "w") as f:
            f.write("# init\n")
        repo.index.add(["init.py"])
        repo.index.commit("initial commit")

        # Test create_branch
        result = create_branch(tmpdir, "fix/test-branch")
        test("create_branch succeeds", result["success"] is True, result["message"])

        # Test get_current_branch
        branch = get_current_branch(tmpdir)
        test("get_current_branch returns branch name", "fix/test-branch" in branch, branch)

        # Add a file and test commit
        new_file = os.path.join(tmpdir, "new_feature.py")
        with open(new_file, "w") as f:
            f.write("def new_feature():\n    pass\n")

        # Test get_changed_files
        changed = get_changed_files(tmpdir)
        test("get_changed_files detects new file", "new_feature.py" in changed, changed)

        # Test commit_changes
        commit_result = commit_changes(tmpdir, "feat: add new feature")
        test("commit_changes succeeds", commit_result["success"] is True, commit_result["message"])

        # After commit, nothing should be changed
        after_commit = get_changed_files(tmpdir)
        test("get_changed_files empty after commit", "new_feature.py" not in after_commit, after_commit)

    finally:
        # Close the repo first — GitPython holds file locks on Windows
        # Without this, shutil.rmtree will crash with PermissionError
        if repo is not None:
            repo.close()

        gc.collect()   # force Python to release remaining file handles
        time.sleep(0.5)  # small wait so Windows fully releases the locks

        def force_remove(func, path, exc):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(tmpdir, onerror=force_remove)

# ─────────────────────────────────────────────────────────────
# TEST: github_tools (no network needed for these)
# ─────────────────────────────────────────────────────────────

def test_github_tools():
    print("\n── GITHUB TOOLS ────────────────────────────────")

    from mcp.tools.github_tools import extract_repo_name, generate_pr_body

    # Test extract_repo_name
    name1 = extract_repo_name("https://github.com/niabob/my-project")
    test("extract_repo_name parses correctly", name1 == "niabob/my-project", name1)

    name2 = extract_repo_name("https://github.com/niabob/my-project.git")
    test("extract_repo_name strips .git", name2 == "niabob/my-project", name2)

    name3 = extract_repo_name("https://github.com/niabob/my-project/")
    test("extract_repo_name strips trailing slash", name3 == "niabob/my-project", name3)

    # Test generate_pr_body
    test_result = {"passed": True, "summary": "3 passed in 0.5s"}
    pr_body = generate_pr_body(
        task="Fix null pointer in login handler",
        changed_files=["src/auth.py", "tests/test_auth.py"],
        test_result=test_result
    )
    test("generate_pr_body returns string", isinstance(pr_body, str))
    test("generate_pr_body includes task", "Fix null pointer" in pr_body)
    test("generate_pr_body includes file names", "auth.py" in pr_body)
    test("generate_pr_body includes test status", "passed" in pr_body.lower())


# ─────────────────────────────────────────────────────────────
# RUN ALL TESTS
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("ASDA-v1 MCP Tool Layer — Manual Tests")
    print("=" * 50)

    test_file_tools()
    test_test_tools()
    test_git_tools()
    test_github_tools()

    print("\n" + "=" * 50)
    print("Done. Fix any FAILs before running the MCP server.")
    print("=" * 50)