"""
file_tools.py
-------------
Tools for reading and writing files in the cloned repository.
These are the most basic tools — the LLM uses these to see code
and to write its fixes back to disk.
"""

import os


def read_file(filepath: str) -> str:
    """
    Read a file and return its full content as a string.

    Args:
        filepath: Full or relative path to the file.
                  Example: "/tmp/cloned_repo/src/auth.py"

    Returns:
        The file content as a string.
        Or an error message if the file doesn't exist.
    """
    # Check if the file actually exists before trying to open it
    if not os.path.exists(filepath):
        return f"ERROR: File not found — {filepath}"

    # Check it's actually a file, not a folder
    if not os.path.isfile(filepath):
        return f"ERROR: Path is a directory, not a file — {filepath}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Tell the LLM how big the file is (useful context)
        line_count = content.count("\n") + 1
        return f"# File: {filepath} ({line_count} lines)\n\n{content}"

    except UnicodeDecodeError:
        return f"ERROR: File is not readable as text (binary file?) — {filepath}"

    except Exception as e:
        return f"ERROR reading file: {str(e)}"


def write_file(filepath: str, content: str) -> str:
    """
    Write content to a file, overwriting what was there before.
    This is how the LLM applies its fixes to the codebase.

    Args:
        filepath: Full or relative path to the file to write.
        content:  The new file content (the fixed code).

    Returns:
        A success message, or an error message.
    """
    try:
        # Create any missing parent directories
        # e.g. if filepath is /tmp/repo/src/utils/helpers.py
        # and src/utils/ doesn't exist yet, this creates it
        parent_dir = os.path.dirname(filepath)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        line_count = content.count("\n") + 1
        return f"SUCCESS: Written {line_count} lines to {filepath}"

    except Exception as e:
        return f"ERROR writing file: {str(e)}"


def list_files(repo_path: str, extension: str = ".py") -> str:
    """
    List all files in the repo with a given extension.
    Useful for the LLM to get an overview of what exists.

    Args:
        repo_path: Root directory of the cloned repo.
        extension: File extension to filter by. Default is ".py"

    Returns:
        A formatted list of all matching file paths.
    """
    if not os.path.exists(repo_path):
        return f"ERROR: Repo path not found — {repo_path}"

    found_files = []

    # Walk through every folder and subfolder
    for root, dirs, files in os.walk(repo_path):

        # Skip hidden folders like .git, __pycache__, .venv
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d != "__pycache__"
            and d != "node_modules"
            and d != ".venv"
            and d != "venv"
        ]

        for filename in files:
            if filename.endswith(extension):
                full_path = os.path.join(root, filename)
                # Show path relative to repo root (cleaner output)
                relative_path = os.path.relpath(full_path, repo_path)
                found_files.append(relative_path)

    if not found_files:
        return f"No {extension} files found in {repo_path}"

    file_list = "\n".join(sorted(found_files))
    return f"Found {len(found_files)} {extension} files:\n\n{file_list}"


def show_diff(original: str, modified: str, filepath: str = "file") -> str:
    """
    Show a unified diff between original and modified content.
    This is the 'diff-first' principle from your abstract —
    the developer sees exactly what will change before it's written.

    Args:
        original: The original file content.
        modified: The proposed new content.
        filepath: Just used for the diff header label.

    Returns:
        A unified diff string showing what changed.
    """
    import difflib

    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"original/{filepath}",
        tofile=f"modified/{filepath}",
        lineterm=""
    ))

    if not diff:
        return "No changes detected between original and modified content."

    return "\n".join(diff)