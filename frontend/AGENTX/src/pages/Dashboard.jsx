import { useState } from "react";
import Header from "../components/Header";
import InputPanel from "../components/InputPanel";
import Sidebar from "../components/Sidebar";
import CodePanel from "../components/CodePanel";
import AnalysisPanel from "../components/AnalysisPanel";
import LogPanel from "../components/LogPanel";

const API_URL = "http://localhost:8000";

function Dashboard() {
  const [repoUrl, setRepoUrl] = useState("");
  const [task, setTask] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [mode, setMode] = useState("ask");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [logs, setLogs] = useState(["Waiting for repository..."]);

  const addLog = (line) => setLogs((prev) => [...prev, line]);

  const handleSubmit = async () => {
    if (!repoUrl.trim() || !task.trim()) {
      setError("Repository URL and task are both required.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedFile(null);
    addLog(`Submitting ${mode} request for ${repoUrl}`);

    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          github_token: githubToken,
          task,
          mode,
        }),
      });

      const data = await response.json();

      if (!data.success) {
        setError(data.error || "Analysis failed.");
        addLog(`Failed: ${data.error || "unknown error"}`);
        return;
      }

      setResult(data);
      if (data.files?.length) {
        setSelectedFile(data.files[0].path);
      }
      addLog("Analysis complete.");
    } catch (err) {
      setError(err.message);
      addLog(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const status = loading ? "running" : error ? "error" : "ready";
  const files = result?.files?.map((f) => f.path) ?? [];

  return (
    <div className="min-h-screen bg-slate-900 text-white">

      <Header status={status} />

      <InputPanel
        repoUrl={repoUrl}
        onRepoUrlChange={setRepoUrl}
        task={task}
        onTaskChange={setTask}
        githubToken={githubToken}
        onGithubTokenChange={setGithubToken}
        mode={mode}
        onModeChange={setMode}
        onSubmit={handleSubmit}
        loading={loading}
      />

      <div className="grid grid-cols-12 gap-4 p-4">

        <div className="col-span-2">
          <Sidebar files={files} selectedFile={selectedFile} onSelectFile={setSelectedFile} />
        </div>

        <div className="col-span-7">
          <CodePanel mode={mode} result={result} selectedFile={selectedFile} />
        </div>

        <div className="col-span-3">
          <AnalysisPanel mode={mode} result={result} loading={loading} error={error} />
        </div>

      </div>

      <LogPanel logs={logs} />

    </div>
  );
}

export default Dashboard;
