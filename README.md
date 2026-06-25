# ASDA-v1 MCP Tool Layer

## File Structure

```
asda_mcp/
├── tools/
│   ├── file_tools.py       # read_file, write_file
│   ├── git_tools.py        # create_branch, commit_changes, push_branch
│   ├── github_tools.py     # open_pull_request
│   └── test_tools.py       # run_tests
├── mcp_server.py           # registers all tools, runs the MCP server
├── test_tools_manually.py  # test every tool without MCP (run this first)
└── .env                    # your GitHub token goes here
```

## Setup

```bash
pip install mcp gitpython PyGithub python-dotenv
```

## .env file

```
GITHUB_TOKEN=your_personal_access_token_here
```

## How to run

```bash
python mcp_server.py
```