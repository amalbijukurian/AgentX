function InputPanel({
  repoUrl,
  onRepoUrlChange,
  task,
  onTaskChange,
  githubToken,
  onGithubTokenChange,
  mode,
  onModeChange,
  onSubmit,
  loading,
}) {
  return (
    <div className="p-6">

      <div className="flex gap-4">

        <input
          type="text"
          value={repoUrl}
          onChange={(e) => onRepoUrlChange(e.target.value)}
          placeholder="GitHub Repository URL"
          className="flex-1 p-3 rounded-lg bg-slate-800 border border-slate-600 focus:outline-none focus:border-cyan-400"
        />

        <input
          type="password"
          value={githubToken}
          onChange={(e) => onGithubTokenChange(e.target.value)}
          placeholder="GitHub Token (optional)"
          className="w-64 p-3 rounded-lg bg-slate-800 border border-slate-600 focus:outline-none focus:border-cyan-400"
        />

        <div className="flex rounded-lg border border-slate-600 overflow-hidden">
          <button
            type="button"
            onClick={() => onModeChange("ask")}
            className={`px-4 font-semibold transition ${
              mode === "ask" ? "bg-cyan-500" : "bg-slate-800 hover:bg-slate-700"
            }`}
          >
            Ask
          </button>
          <button
            type="button"
            onClick={() => onModeChange("edit")}
            className={`px-4 font-semibold transition ${
              mode === "edit" ? "bg-cyan-500" : "bg-slate-800 hover:bg-slate-700"
            }`}
          >
            Edit
          </button>
        </div>

        <button
          onClick={onSubmit}
          disabled={loading}
          className="bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-600 disabled:cursor-not-allowed px-6 rounded-lg font-semibold transition"
        >
          {loading ? "Analyzing..." : "Analyze Repository"}
        </button>

      </div>

      <textarea
        rows="4"
        value={task}
        onChange={(e) => onTaskChange(e.target.value)}
        placeholder="Describe the task..."
        className="w-full mt-4 p-3 rounded-lg bg-slate-800 border border-slate-600 focus:outline-none focus:border-cyan-400"
      />

    </div>
  );
}

export default InputPanel;
