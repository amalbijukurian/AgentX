from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.models import AnalyzeRequest
from RAG_and_Agents.agent import Agent


app = FastAPI(
    title="AgentX API",
    version="1.0.0"
)


# -----------------------------
# CORS
# -----------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Root
# -----------------------------

@app.get("/")
def home():
    return {
        "message": "AgentX Backend Running"
    }


# -----------------------------
# Health Check
# -----------------------------

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# -----------------------------
# Analyze Repository
# -----------------------------

@app.post("/analyze")
def analyze(request: AnalyzeRequest):

    try:

        agent = Agent()

        result = agent.run(
            repo_url=request.repo_url,
            token=request.github_token,
            task=request.task,
            mode=request.mode
        )

        return result

    except Exception as e:

        return {
            "success": False,
            "diagnosis": "",
            "files": [],
            "test_result": {},
            "pr_url": "",
            "error": str(e)
        }