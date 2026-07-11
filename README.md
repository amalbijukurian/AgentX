# AgentX — ASDA v1

**Autonomous Software Development Agent** — point it at a GitHub repository, describe a bug or task in plain English, and it will find the relevant code, generate a fix, run the tests, and open a pull request. Or just ask it questions about how the codebase works.

---

## How it works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────┐
│   Frontend   │ --> │   Backend    │ --> │            Agent             │
│ React + Vite │     │   FastAPI    │     │                              │
│  (Dashboard) │     │  /analyze    │     │  1. RAG   — clone + index    │
└──────────────┘     └──────────────┘     │  2. LLM   — diagnose + fix   │
                                          │  3. Tools — write, test,     │
                                          │             commit, PR       │
                                          └──────────────────────────────┘
```

1. **RAG pipeline** ([RAG_and_Agents/rag.py](RAG_and_Agents/rag.py)) — clones the target repo, chunks source files by function/class using tree-sitter AST parsing, embeds the chunks with sentence-transformers, and stores them in ChromaDB. The task description is used to retrieve the most relevant chunks.
2. **LLM layer** ([RAG_and_Agents/llm.py](RAG_and_Agents/llm.py)) — sends the retrieved code + task to `openai/gpt-oss-120b` via the Groq API and parses a structured JSON response (diagnosis, corrected files, PR title/body).
3. **Tool layer** ([RAG_and_Agents/tools.py](RAG_and_Agents/tools.py) → [mcp/tools/](mcp/tools/)) — writes the generated files, runs the repo's pytest suite (retrying the LLM up to 3 times on failures), creates a branch, commits, pushes, and opens the pull request via the GitHub API.

### Modes

| Mode | What it does |
|------|--------------|
| `edit` | Full pipeline: diagnose → fix → test → commit → open PR |
| `ask`  | Q&A only: answers questions about the codebase with file/function references, changes nothing |

---

## Project structure

```
AgentX/
├── RAG_and_Agents/       # Core agent: RAG pipeline, LLM layer, orchestrator
│   ├── agent.py          #   Orchestrator (also runnable as a CLI)
│   ├── rag.py            #   Clone, AST-chunk, embed, retrieve (ChromaDB)
│   ├── llm.py            #   Groq LLM calls + response parsing
│   ├── tools.py          #   Bridge from agent.py to mcp/tools/*
│   └── .env              #   GROQ_API_KEY lives here (not committed)
├── mcp/                  # Tool implementations + MCP server
│   ├── tools/            #   file / git / github / test tools
│   ├── mcp_server.py     #   Exposes the tools over MCP
│   └── test_tools_manually.py
├── backend/              # FastAPI server wrapping the agent
│   ├── main.py           #   /, /health, /analyze
│   └── models.py         #   Request/response schemas
├── frontend/AGENTX/      # React 19 + Vite + Tailwind dashboard
└── venv/                 # Single Python 3.10 venv for the whole project
```

---

## Setup

### Prerequisites

- Python 3.10
- Node.js 18+
- A [Groq API key](https://console.groq.com/keys) (free tier works)
- A GitHub personal access token (only needed for `edit` mode / private repos)

### 1. Python environment (one venv for everything)

```powershell
cd AgentX
py -3.10 -m venv venv
venv\Scripts\activate
pip install -r RAG_and_Agents\requirements.txt -r mcp\requirements.txt -r backend\requirements.txt
```

### 2. API key

Create `RAG_and_Agents\.env`:

```
GROQ_API_KEY=your_groq_key_here
```

The GitHub token is **not** stored in `.env` — it's supplied per request from the dashboard or CLI.

### 3. Run the backend

```powershell
venv\Scripts\activate
cd backend
uvicorn main:app --reload
```

Server starts on `http://localhost:8000` — check `http://localhost:8000/health`.

### 4. Run the frontend

```powershell
cd frontend\AGENTX
npm install
npm run dev
```

Dashboard opens on `http://localhost:5173` (the backend's CORS is configured for this origin).

---

## Usage

### From the dashboard

Enter the repo URL, your GitHub token, and a task description; pick **Ask** or **Edit** mode and submit. Results (diagnosis, changed files, test status, PR link) appear in the panels.

### From the CLI

```powershell
cd RAG_and_Agents
python agent.py --repo https://github.com/owner/repo --task "fix the divide by zero in utils/math.py"
python agent.py --repo https://github.com/owner/repo --task "what does this project do" --mode ask
```

### From the API

```
POST http://localhost:8000/analyze
{
  "repo_url":     "https://github.com/owner/repo",
  "github_token": "ghp_...",
  "task":         "fix the divide by zero in utils/math.py",
  "mode":         "edit"        // or "ask"
}
```

Response (edit mode): `{ success, diagnosis, files, test_result, pr_url, error }`
Response (ask mode): `{ success, answer, references, confidence, note }`

---

## Testing

```powershell
venv\Scripts\activate

# Tool layer (25 tests, no network needed)
cd mcp
python test_tools_manually.py

# RAG pipeline (interactive — indexes a real repo)
cd ..\RAG_and_Agents
python test_rag.py

# LLM layer (one live Groq call with fake chunks)
python test_llm.py
```

---

## Tech stack

| Layer | Tech |
|-------|------|
| Retrieval | ChromaDB, sentence-transformers, tree-sitter (AST chunking) |
| LLM | Groq API (`openai/gpt-oss-120b`) via the OpenAI SDK |
| Git/GitHub | GitPython, PyGithub |
| Backend | FastAPI, uvicorn, pydantic |
| Frontend | React 19, Vite 7, Tailwind CSS 4 |
| Tooling | MCP (Model Context Protocol) server, pytest |

## Known limitations

- **Edit mode confirms in the terminal.** Before writing files, the agent prints a diff and waits for a `y/n` on stdin — fine for CLI use, but when triggered through the API the confirmation happens in the backend's terminal, not the browser.
- The target repo needs a pytest-compatible test suite for the verify-and-retry loop to be meaningful; repos without tests are treated as passing.
- Supported languages for AST chunking depend on tree-sitter grammars; unsupported files are skipped during indexing.
