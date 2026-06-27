"""
mcp_server.py
-------------
This is the main file. It starts the MCP server and registers
all tools so the LLM can call them.

Run this with:
    python mcp_server.py

The LLM (Claude/GPT) connects to this server and can then
call any of the registered tools by name.
"""

import os
import asyncio
from dotenv import load_dotenv

# MCP framework
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Our tool functions
from mcp.tools.file_tools import read_file, write_file, list_files, show_diff
from mcp.tools.test_tools import run_tests, format_test_result
from mcp.tools.git_tools import (
    clone_repository,
    create_branch,
    commit_changes,
    push_branch,
    get_current_branch,
    get_changed_files
)
from mcp.tools.github_tools import (
    open_pull_request,
    extract_repo_name,
    generate_pr_body
)

# Load environment variables from .env file
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# ─────────────────────────────────────────────
# Create the MCP server
# ─────────────────────────────────────────────
app = Server("asda-v1")


# ─────────────────────────────────────────────
# FILE TOOLS
# ─────────────────────────────────────────────

@app.tool()
async def tool_read_file(filepath: str) -> str:
    """
    Read a file from the cloned repository and return its content.
    Use this before making any changes — always read first.

    Args:
        filepath: Full path to the file. Example: "/tmp/repo/src/auth.py"
    """
    return read_file(filepath)


@app.tool()
async def tool_write_file(filepath: str, content: str) -> str:
    """
    Write content to a file, replacing its current content.
    Only call this AFTER showing the diff to the developer and getting confirmation.

    Args:
        filepath: Full path to the file to write.
        content:  The new file content (the fixed/improved code).
    """
    return write_file(filepath, content)


@app.tool()
async def tool_list_files(repo_path: str, extension: str = ".py") -> str:
    """
    List all files in the repo with a given extension.
    Use this at the start to understand the structure of the codebase.

    Args:
        repo_path: Root directory of the cloned repo. Example: "/tmp/repo"
        extension: File type to list. Default is ".py"
    """
    return list_files(repo_path, extension)


@app.tool()
async def tool_show_diff(original: str, modified: str, filepath: str = "file") -> str:
    """
    Show a diff between original and modified file content.
    ALWAYS call this before writing any file — show the developer what will change.

    Args:
        original: The current file content (before changes).
        modified: The proposed new content (after changes).
        filepath: The filename, used only for the diff header label.
    """
    return show_diff(original, modified, filepath)


# ─────────────────────────────────────────────
# TEST TOOLS
# ─────────────────────────────────────────────

@app.tool()
async def tool_run_tests(repo_path: str) -> str:
    """
    Run the pytest test suite in the repository.
    Call this after writing fixes. If tests fail, read the output and fix again.

    Args:
        repo_path: Root directory of the cloned repo. Example: "/tmp/repo"
    """
    result = run_tests(repo_path)
    return format_test_result(result)


# ─────────────────────────────────────────────
# GIT TOOLS
# ─────────────────────────────────────────────

@app.tool()
async def tool_clone_repository(github_url: str, clone_to: str) -> str:
    """
    Clone a GitHub repository to a local path.
    This must be the first thing done before any other tool.

    Args:
        github_url: The GitHub repository URL. Example: "https://github.com/user/repo"
        clone_to:   Where to clone it. Example: "/tmp/my-repo"
    """
    result = clone_repository(github_url, clone_to)
    return result["message"]


@app.tool()
async def tool_create_branch(repo_path: str, branch_name: str) -> str:
    """
    Create a new git branch and switch to it.
    Always create a branch before making any changes. Never commit to main directly.

    Args:
        repo_path:   Path to the cloned repo. Example: "/tmp/repo"
        branch_name: Name for the new branch. Example: "fix/login-bug"
    """
    result = create_branch(repo_path, branch_name)
    return result["message"]


@app.tool()
async def tool_commit_changes(repo_path: str, commit_message: str) -> str:
    """
    Stage all modified files and commit them.
    Only call this after tests pass and developer has confirmed the changes.

    Args:
        repo_path:      Path to the cloned repo. Example: "/tmp/repo"
        commit_message: Descriptive commit message. Example: "fix: handle null user in auth"
    """
    result = commit_changes(repo_path, commit_message)
    return result["message"]


@app.tool()
async def tool_push_branch(repo_path: str, branch_name: str, remote_url: str) -> str:
    """
    Push the local branch to GitHub.
    Call this after committing, before opening the PR.

    Args:
        repo_path:   Path to the cloned repo. Example: "/tmp/repo"
        branch_name: Branch to push. Example: "fix/login-bug"
        remote_url:  The GitHub repo URL. Example: "https://github.com/user/repo"
    """
    if not GITHUB_TOKEN:
        return "ERROR: GITHUB_TOKEN not found in .env file"

    result = push_branch(repo_path, branch_name, GITHUB_TOKEN, remote_url)
    return result["message"]


@app.tool()
async def tool_get_changed_files(repo_path: str) -> str:
    """
    List all files that have been modified but not yet committed.
    Useful to check what the agent has changed so far.

    Args:
        repo_path: Path to the cloned repo. Example: "/tmp/repo"
    """
    return get_changed_files(repo_path)


# ─────────────────────────────────────────────
# GITHUB PR TOOL
# ─────────────────────────────────────────────

@app.tool()
async def tool_open_pull_request(
    github_url: str,
    branch_name: str,
    pr_title: str,
    pr_body: str,
    base_branch: str = "main"
) -> str:
    """
    Open a Pull Request on GitHub.
    This is the final step. Call this after pushing the branch.

    Args:
        github_url:  The GitHub repo URL. Example: "https://github.com/user/repo"
        branch_name: The branch with the agent's changes. Example: "fix/login-bug"
        pr_title:    Title of the PR. Example: "fix: resolve null pointer in login"
        pr_body:     Description of what was changed and why.
        base_branch: Branch to merge into. Default is "main".
    """
    if not GITHUB_TOKEN:
        return "ERROR: GITHUB_TOKEN not found in .env file"

    repo_full_name = extract_repo_name(github_url)
    if not repo_full_name:
        return f"ERROR: Could not parse repo name from URL: {github_url}"

    result = open_pull_request(
        github_token=GITHUB_TOKEN,
        repo_full_name=repo_full_name,
        branch_name=branch_name,
        pr_title=pr_title,
        pr_body=pr_body,
        base_branch=base_branch
    )

    if result["success"]:
        return f"Pull Request created successfully!\nURL: {result['pr_url']}"
    else:
        return f"Failed to create PR: {result['message']}"


# ─────────────────────────────────────────────
# Start the server
# ─────────────────────────────────────────────

async def main():
    print("ASDA-v1 MCP Server starting...")
    print("Registered tools:")
    print("  - tool_read_file")
    print("  - tool_write_file")
    print("  - tool_list_files")
    print("  - tool_show_diff")
    print("  - tool_run_tests")
    print("  - tool_clone_repository")
    print("  - tool_create_branch")
    print("  - tool_commit_changes")
    print("  - tool_push_branch")
    print("  - tool_get_changed_files")
    print("  - tool_open_pull_request")
    print("\nServer ready. Waiting for LLM to connect...")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())