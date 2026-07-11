function LogPanel({ logs }) {
  return (
    <div className="m-4 bg-slate-800 rounded-xl p-4">

      <h2 className="text-xl font-bold mb-4">
         Logs
      </h2>

      <div className="space-y-2">

        {logs.map((log, index) => (
          <div
            key={index}
            className="text-slate-300"
          >
             {log}
          </div>
        ))}

      </div>

    </div>
  );
}

export default LogPanel;
