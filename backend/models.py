from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    repo_url: str
    github_token: str
    task: str
    mode: str = "edit"


class AnalyzeResponse(BaseModel):
    success: bool
    diagnosis: str | None = None
    files: list = []
    test_result: dict | None = None
    pr_url: str | None = None
    error: str | None = None