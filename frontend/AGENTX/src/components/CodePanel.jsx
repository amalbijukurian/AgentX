function CodePanel({ mode, result, selectedFile }) {
  const file = result?.files?.find((f) => f.path === selectedFile);

  return (
    <div className="bg-slate-800 rounded-xl p-4 h-[500px] overflow-y-auto">
      <h2 className="font-bold text-xl mb-3">
        Code Viewer
      </h2>

      {mode === "edit" && file && (
        <pre className="text-sm text-slate-200 whitespace-pre-wrap bg-slate-900 rounded-lg p-3">
          {file.new_code}
        </pre>
      )}

      {mode === "edit" && !file && (
        <p className="text-sm text-slate-400">
          {result?.files?.length
            ? "Select a file from the sidebar to view its proposed code."
            : "No files to show yet — run an analysis."}
        </p>
      )}

      {mode === "ask" && (
        <p className="text-sm text-slate-400">
          Ask mode doesn't change files — see the Analysis panel for the answer.
        </p>
      )}
    </div>
  );
}

export default CodePanel;
