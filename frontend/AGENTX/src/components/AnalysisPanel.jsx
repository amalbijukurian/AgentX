function AnalysisPanel({ mode, result, loading, error }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 h-[500px] overflow-y-auto">

      <h2 className="text-xl font-bold mb-5">
         AI Analysis
      </h2>

      <div className="space-y-4">

        <div className="bg-slate-700 p-3 rounded-lg">
          <h3 className="font-semibold text-cyan-400">
            Status
          </h3>
          <p className="text-sm text-slate-300">
            {loading ? "Analyzing..." : error ? "Failed" : result ? "Done" : "Waiting for analysis..."}
          </p>
        </div>

        {error && (
          <div className="bg-slate-700 p-3 rounded-lg">
            <h3 className="font-semibold text-red-400">
              Error
            </h3>
            <p className="text-sm text-slate-300">{error}</p>
          </div>
        )}

        {result && mode === "ask" && (
          <>
            <div className="bg-slate-700 p-3 rounded-lg">
              <h3 className="font-semibold text-cyan-400">
                Answer
              </h3>
              <p className="text-sm text-slate-300 whitespace-pre-wrap">
                {result.answer}
              </p>
            </div>
            <div className="bg-slate-700 p-3 rounded-lg">
              <h3 className="font-semibold text-cyan-400">
                Confidence
              </h3>
              <p className="text-sm text-slate-300">{result.confidence}</p>
            </div>
          </>
        )}

        {result && mode === "edit" && (
          <>
            <div className="bg-slate-700 p-3 rounded-lg">
              <h3 className="font-semibold text-cyan-400">
                Diagnosis
              </h3>
              <p className="text-sm text-slate-300 whitespace-pre-wrap">
                {result.diagnosis}
              </p>
            </div>
            <div className="bg-slate-700 p-3 rounded-lg">
              <h3 className="font-semibold text-cyan-400">
                Tests
              </h3>
              <p className="text-sm text-slate-300">
                {result.test_result?.passed ? "Passed" : "Failed / not run"}
              </p>
            </div>
            {result.pr_url && (
              <div className="bg-slate-700 p-3 rounded-lg">
                <h3 className="font-semibold text-cyan-400">
                  Pull Request
                </h3>
                <a
                  href={result.pr_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-cyan-300 underline break-all"
                >
                  {result.pr_url}
                </a>
              </div>
            )}
          </>
        )}

      </div>

    </div>
  );
}

export default AnalysisPanel;
