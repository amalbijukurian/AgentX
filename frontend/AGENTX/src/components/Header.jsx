function Header({ status }) {
  const dotColor =
    status === "error" ? "bg-red-500" : status === "running" ? "bg-yellow-400" : "bg-green-500";
  const textColor =
    status === "error" ? "text-red-400" : status === "running" ? "text-yellow-300" : "text-green-400";
  const label = status === "error" ? "Error" : status === "running" ? "Running" : "Ready";

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700 bg-slate-900">

      <div className="flex items-center gap-3">
        <span className="text-3xl"></span>

        <div>
          <h1 className="text-3xl font-bold text-cyan-400">
            AgentX
          </h1>

          <p className="text-sm text-slate-400">
            Autonomous Software Development Agent
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className={`w-3 h-3 rounded-full ${dotColor}`}></div>

        <span className={`font-medium ${textColor}`}>
          {label}
        </span>
      </div>

    </header>
  );
}

export default Header;
