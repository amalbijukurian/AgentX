function AnalysisPanel() {
  return (
    <div className="bg-slate-800 rounded-xl p-4 h-[500px]">

      <h2 className="text-xl font-bold mb-5">
         AI Analysis
      </h2>

      <div className="space-y-4">

        <div className="bg-slate-700 p-3 rounded-lg">
          <h3 className="font-semibold text-cyan-400">
            Repository
          </h3>

          <p className="text-sm text-slate-300">
            Waiting for analysis...
          </p>
        </div>

        <div className="bg-slate-700 p-3 rounded-lg">
          <h3 className="font-semibold text-cyan-400">
            Suggested Fix
          </h3>

          <p className="text-sm text-slate-300">
            —
          </p>
        </div>

      </div>

    </div>
  );
}

export default AnalysisPanel;