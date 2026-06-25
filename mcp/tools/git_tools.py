"""
git_tools.py
------------
Tools for local git operations inside the cloned repository.
Handles: creating branches, staging files, committing, pushing.

Uses GitPython library.
Install: pip install gitpython
"""

import os
import git  # GitPython


def clone_repository(github_url: str, clone_to: str) -> dict:
    """
    Clone a GitHub repository to a local folder.
    This is the very first step — before anything else can happen.

    Args:
        github_url: The GitHub repo URL.
                    Example: "https://github.com/user/my-repo"
        clone_to:   Where to clone it on disk.
                    Example: "/tmp/my-repo"

    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    try:
        # If folder already exists, don't clone again
        if os.path.exists(clone_to):
            return {
                "success": True,
                "message": f"Repo already exists at {clone_to} — skipping clone"
            }

        print(f"Cloning {github_url} into {clone_to} ...")
        git.Repo.clone_from(github_url, clone_to)

        return {
            "success": True,
            "message": f"Successfully cloned to {clone_to}"
        }

    except git.GitCommandError as e:
        return {
            "success": False,
            "message": f"Git clone failed: {str(e)}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error during clone: {str(e)}"
        }


def create_branch(repo_path: str, branch_name: str) -> dict:
    """
    Create a new branch in the local repository and switch to it.
    All the agent's changes will go on this branch, not on main.

    Args:
        repo_path:   Path to the cloned repo on disk.
        branch_name: Name for the new branch.
                     Example: "fix/login-null-check"

    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    try:
        repo = git.Repo(repo_path)

        # Check if branch already exists
        existing_branches = [b.name for b in repo.branches]
        if branch_name in existing_branches:
            # Just switch to it instead of creating
            repo.git.checkout(branch_name)
            return {
                "success": True,
                "message": f"Switched to existing branch: {branch_name}"
            }

        # Create and immediately switch to the new branch
        repo.git.checkout("-b", branch_name)

        return {
            "success": True,
            "message": f"Created and switched to branch: {branch_name}"
        }

    except git.GitCommandError as e:
        return {
            "success": False,
            "message": f"Git branch creation failed: {str(e)}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error: {str(e)}"
        }


def commit_changes(repo_path: str, commit_message: str) -> dict:
    """
    Stage ALL modified files and commit them with a message.
    Only call this AFTER the developer has confirmed the diff
    and tests have passed.

    Args:
        repo_path:      Path to the cloned repo on disk.
        commit_message: The commit message.
                        Example: "fix: add null check in login handler"

    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    try:
        repo = git.Repo(repo_path)

        # Check if there's anything to commit
        if not repo.is_dirty(untracked_files=True):
            return {
                "success": False,
                "message": "Nothing to commit — no changes detected in repo"
            }

        # Stage all changes (modified + new files)
        repo.git.add("--all")

        # Commit with the provided message
        commit = repo.index.commit(commit_message)

        return {
            "success": True,
            "message": f"Committed successfully. Commit hash: {commit.hexsha[:7]}"
        }

    except git.GitCommandError as e:
        return {
            "success": False,
            "message": f"Git commit failed: {str(e)}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error: {str(e)}"
        }


def push_branch(repo_path: str, branch_name: str, github_token: str, remote_url: str) -> dict:
    """
    Push the local branch to GitHub.
    We inject the token into the URL so no separate auth step is needed.

    Args:
        repo_path:    Path to the cloned repo on disk.
        branch_name:  Name of the branch to push.
        github_token: Personal Access Token from your .env file.
        remote_url:   The repo's GitHub URL.
                      Example: "https://github.com/user/my-repo"

    Returns:
        dict with 'success' (bool) and 'message' (str)
    """
    try:
        repo = git.Repo(repo_path)

        # Build authenticated URL
        # Turns: https://github.com/user/repo
        # Into:  https://TOKEN@github.com/user/repo
        if "https://" in remote_url:
            auth_url = remote_url.replace(
                "https://",
                f"https://{github_token}@"
            )
        else:
            return {
                "success": False,
                "message": "Only HTTPS GitHub URLs are supported (not SSH)"
            }

        # Set or update the remote origin URL with token
        try:
            origin = repo.remote("origin")
            origin.set_url(auth_url)
        except ValueError:
            repo.create_remote("origin", auth_url)

        # Push the branch
        repo.git.push("origin", branch_name)

        return {
            "success": True,
            "message": f"Branch '{branch_name}' pushed to GitHub successfully"
        }

    except git.GitCommandError as e:
        return {
            "success": False,
            "message": f"Git push failed: {str(e)}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Unexpected error during push: {str(e)}"
        }


def get_current_branch(repo_path: str) -> str:
    """
    Return the name of the currently active branch.
    Useful for the LLM to confirm it's on the right branch.
    """
    try:
        repo = git.Repo(repo_path)
        return repo.active_branch.name
    except Exception as e:
        return f"ERROR: {str(e)}"


def get_changed_files(repo_path: str) -> str:
    """
    Return a list of files that have been modified but not yet committed.
    Useful for the LLM to know what it has changed so far.
    """
    try:
        repo = git.Repo(repo_path)
        changed = [item.a_path for item in repo.index.diff(None)]
        untracked = repo.untracked_files

        all_changed = changed + list(untracked)

        if not all_changed:
            return "No modified files detected"

        return "Modified files:\n" + "\n".join(all_changed)

    except Exception as e:
        return f"ERROR: {str(e)}"