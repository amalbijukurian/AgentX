"""
tools.py
--------
ToolLayer — the bridge between agent.py and the tool implementations
already built in mcp/tools/*.py.

Implements the frozen interface contract from PROGRESS.md:
    write_file(path, content)
    run_tests(repo_path)        -> { passed, output }
    git_branch(branch)
    git_commit(files, message)
    create_pr(token, title, body, branch, repo_url) -> pr_url

Lives alongside agent.py (RAG_and_Agents/) because agent.py's
`from tools import ToolLayer` resolves against its own script directory
when run directly as `python agent.py` from inside RAG_and_Agents/.

mcp/tools/*.py is loaded by file path (not `import mcp.tools...`) so this
never collides with the `mcp` pip package (the MCP SDK used by mcp_server.py).
"""

import importlib.util
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MCP_TOOLS_DIR = os.path.join(_THIS_DIR, "..", "mcp", "tools")


def _load(module_name: str, filename: str):
    path = os.path.join(_MCP_TOOLS_DIR, filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_file_tools = _load("asda_mcp_file_tools", "file_tools.py")
_git_tools = _load("asda_mcp_git_tools", "git_tools.py")
_github_tools = _load("asda_mcp_github_tools", "github_tools.py")
_test_tools = _load("asda_mcp_test_tools", "test_tools.py")


class ToolLayer:
    """Adapts mcp/tools/* functions to the interface agent.py expects."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def write_file(self, path: str, content: str):
        full_path = path if os.path.isabs(path) else os.path.join(self.repo_path, path)
        result = _file_tools.write_file(full_path, content)
        if result.startswith("ERROR"):
            raise RuntimeError(result)

    def run_tests(self, repo_path: str) -> dict:
        result = _test_tools.run_tests(repo_path)
        return {"passed": result["passed"], "output": result["output"]}

    def git_branch(self, branch: str):
        result = _git_tools.create_branch(self.repo_path, branch)
        if not result["success"]:
            raise RuntimeError(result["message"])

    def git_commit(self, files: list, message: str):
        result = _git_tools.commit_changes(self.repo_path, message)
        if not result["success"]:
            raise RuntimeError(result["message"])

    def create_pr(self, token: str, title: str, body: str, branch: str, repo_url: str) -> str:
        push_result = _git_tools.push_branch(self.repo_path, branch, token, repo_url)
        if not push_result["success"]:
            raise RuntimeError(push_result["message"])

        repo_full_name = _github_tools.extract_repo_name(repo_url)
        pr_result = _github_tools.open_pull_request(
            github_token=token,
            repo_full_name=repo_full_name,
            branch_name=branch,
            pr_title=title,
            pr_body=body,
        )
        if not pr_result["success"]:
            raise RuntimeError(pr_result["message"])

        return pr_result["pr_url"]
