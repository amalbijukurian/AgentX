# ASDA v1 — Day 1 Progress Log
**Date:** June 24, 2026
**Session:** Full build kickoff

---

## What was built today

### 1. `rag.py` — RAG Pipeline ✅ DONE + TESTED
The foundation of the whole system. Clones a GitHub repo, indexes the codebase into ChromaDB, retrieves relevant code chunks for any natural language query.

**Key features built:**
- `RAGPipeline.index(repo_url, token)` — clone + chunk + embed + store
- `RAGPipeline.retrieve(task, k)` — embed query + semantic search → top-k chunks
- `RAGPipeline.get_file(path)` — read any file from cloned repo
- `RAGPipeline.cleanup()` — remove temp dirs on exit

**Chunking strategy (3-tier fallback):**
1. tree-sitter universal AST — extracts functions/classes for 10+ languages
2. Python built-in `ast` module — fallback if tree-sitter not installed
3. Fixed 60-line windows — last resort for unsupported file types

**Languages supported:**
`.py .js .jsx .ts .tsx .java .go .rb .rs .cpp .c .h`

**Smart clone caching:**
- First run → `git clone --depth=1` into `.asda/repos/<repo-slug>/`
- Repeat run → `git pull` (no re-clone, no temp folder piling up)
- Repos stored in `.asda/repos/` — not system temp
- `atexit` cleanup registered automatically

**Tested on:** Expo-Lead-Capture repo (JavaScript/React Native)

---

### 2. `llm.py` — LLM Layer ✅ DONE + TESTED
The AI brain. Sends retrieved code chunks to OpenAI GPT-4o and gets back structured responses.

**Two modes:**

**Edit mode — `llm.analyse(chunks, task, repo_path)`**
- Builds a structured system prompt with task + retrieved chunks
- Calls GPT-4o with `response_format: json_object` (forces valid JSON)
- Parses response → `{ diagnosis, files, pr_title, pr_body }`
- Attaches original file content from disk for diffing
- `temperature=0.2` for deterministic code output

**Ask mode — `llm.answer(chunks, question)`**
- Separate Q&A system prompt — answer only, no code changes
- Returns `{ answer, references, confidence, note }`

**Retry on test failure — `llm.retry(task, previous_result, test_output)`**
- Re-prompts LLM with original task + previous generated code + test failure output
- Same return structure as `analyse()` — agent treats it identically

**Display helpers:**
- `llm.show_diagnosis(result)` — pretty print diagnosis to terminal
- `llm.show_diff(result)` — unified diff + y/n confirmation gate
- `llm.show_answer(result)` — pretty print Q&A answer with references

**Tested with:** fake divide-by-zero chunks via `test_llm.py`

---

### 3. `agent.py` — Orchestrator ✅ DONE
The glue that connects rag.py → llm.py → tools.py in sequence.

**Two modes via `--mode` flag:**

**`--mode ask` (Q&A)**
```
rag.index() → rag.retrieve() → llm.answer() → print answer
```

**`--mode edit` (default — make code changes)**
```
rag.index() → rag.retrieve() → llm.analyse() → llm.show_diff()
→ confirm y/n → tools.write_file() → tools.run_tests()
→ [retry loop if fail] → tools.git_branch() → tools.git_commit()
→ tools.create_pr() → print PR URL
```

**Key features:**
- `Agent.run(repo_url, token, task, mode)` — single entry point
- `_run_ask()` — handles ask mode
- `_run_edit()` — handles edit mode (write + test + git + PR)
- `_run_with_retry()` — up to 3 LLM retry attempts on test failure
- `_branch_name(task)` — generates `asda/fix-divide-by-zero-error` from task string
- `ToolStub` — simulates tools.py until Member 2 builds it
- CLI: `python agent.py --repo URL --task "..." --mode ask|edit`

---

### 4. `test_rag.py` — RAG smoke test ✅ DONE
Tests RAG pipeline end to end independently. Asks for repo URL + task, prints top-k retrieved chunks with scores.

### 5. `test_llm.py` — LLM smoke test ✅ DONE
Tests LLM layer independently using fake chunks. No repo needed. Prints diagnosis, generated code, diff.

### 6. `requirements.txt` ✅ DONE
```
chromadb
sentence-transformers
tree-sitter
tree-sitter-language-pack
openai
httpx
PyGithub
gitpython
fastapi
uvicorn
python-dotenv
```

### 7. `.env.example` + `.gitignore` ✅ DONE

---

## Current file ownership

| File | Owner | Status |
|---|---|---|
| `rag.py` | You | ✅ Done + tested |
| `llm.py` | You | ✅ Done + tested |
| `agent.py` | You | ✅ Done |
| `tools.py` | Member 2 | ⏳ Not started |
| `api.py` | Member 2 | ⏳ Not started |
| React app | Member 3 | ⏳ Not started |

---

## Interface contracts (freeze these — don't change)

These are the function signatures your teammates depend on:

```python
# rag.py → agent.py (you call these yourself)
rag.index(repo_url: str, token: str) → { files, chunks, skipped, repo_path }
rag.retrieve(task: str, k=6) → [{ text, file, name, lines, score }]

# llm.py → agent.py (you call these yourself)
llm.analyse(chunks, task, repo_path) → { diagnosis, files, pr_title, pr_body }
llm.answer(chunks, question) → { answer, references, confidence, note }
llm.retry(task, previous_result, test_output) → { diagnosis, files, pr_title, pr_body }

# agent.py → api.py (Member 2 calls this from FastAPI)
agent.run(repo_url, token, task, mode="edit") → { success, mode, ..., error }

# tools.py → agent.py (Member 2 must implement these exactly)
tools.write_file(path: str, content: str)
tools.run_tests(repo_path: str) → { passed: bool, output: str }
tools.git_branch(branch: str)
tools.git_commit(files: list, message: str)
tools.create_pr(token, title, body, branch, repo_url) → str  # PR URL
```

---

## Bugs fixed today

| Bug | Fix |
|---|---|
| `openai` version conflict (`proxies` error) | `pip install --upgrade openai httpx` |
| Repo with no `.py` files → crash | Added multi-language support + empty index guard |
| `list index out of range` on empty index | Added `collection.count() == 0` check in `retrieve()` |
| Temp folders piling up in system temp | Smart clone cache in `.asda/repos/` + `git pull` on repeat |
| `KeyError: 'pr_url'` in ask mode | `main()` now checks mode before printing result |
| JS/TS repos not indexed | Added tree-sitter universal AST chunker |

---

## What to do tomorrow (Day 2)

### Your tasks
- [ ] Test `--mode ask` on a real repo end to end
- [ ] Test `--mode edit` on a simple Python repo (needs tools.py from Member 2)
- [ ] Wire `agent.py` to Member 2's `tools.py` once they deliver it
- [ ] Run full pipeline on demo repo — verify PR opens on GitHub
- [ ] Prompt tune `llm.py` system prompt if generated code quality is poor

### Member 2 tasks (tools.py + api.py)
- [ ] `ToolLayer.__init__(repo_path)` — init with cloned repo path
- [ ] `write_file(path, content)` — write file to disk, backup original
- [ ] `run_tests(repo_path)` → `{ passed, output }` — subprocess pytest
- [ ] `git_branch(branch)` — GitPython create + checkout branch
- [ ] `git_commit(files, message)` — stage + commit
- [ ] `create_pr(token, title, body, branch, repo_url)` → PR URL — PyGitHub
- [ ] `api.py` — FastAPI wrapper: `POST /run` calls `agent.run()`
- [ ] Enable CORS for React dev server (port 3000)

### Member 3 tasks (React frontend)
- [ ] Input fields: repo URL, GitHub PAT, task text, mode toggle (ask/edit)
- [ ] POST to `http://localhost:8000/run` on submit
- [ ] Stub the API response on Day 1 so UI can be built independently
- [ ] Display: answer panel (ask mode), diff viewer + PR link (edit mode)
- [ ] Plug into real `api.py` on Day 2

---

## How to run tomorrow

```bash
# activate venv first
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

# ask mode — question about a repo
python agent.py \
  --repo https://github.com/owner/repo \
  --task "what does this repo do" \
  --mode ask

# edit mode — make a code change
python agent.py \
  --repo https://github.com/owner/repo \
  --task "fix the null check in auth.py" \
  --mode edit

# test RAG independently
python test_rag.py

# test LLM independently
python test_llm.py
```

---

## Key things to remember


**`.env` file** must have:
```
OPENAI_API_KEY=sk-proj-...
```

**tools.py is not built yet** — agent.py uses `ToolStub` as a fallback which simulates tool calls without actually writing files or creating PRs. The stub is automatically replaced when Member 2's `tools.py` is present.

**Repo cache** lives in `.asda/repos/` — delete this folder to force a fresh clone.

---

*ASDA v1 — Day 1 complete*