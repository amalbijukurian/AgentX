function InputPanel() {
  return (
    <div className="p-6">

      <div className="flex gap-4">

        <input
          type="text"
          placeholder="GitHub Repository URL"
          className="flex-1 p-3 rounded-lg bg-slate-800 border border-slate-600 focus:outline-none focus:border-cyan-400"
        />

        <button className="bg-cyan-500 hover:bg-cyan-600 px-6 rounded-lg font-semibold transition">
          Analyze Repository
        </button>

      </div>

      <textarea
        rows="4"
        placeholder="Describe the task..."
        className="w-full mt-4 p-3 rounded-lg bg-slate-800 border border-slate-600 focus:outline-none focus:border-cyan-400"
      />

    </div>
  );
}

export default InputPanel;