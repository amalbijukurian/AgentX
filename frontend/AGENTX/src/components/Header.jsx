function Header() {
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
        <div className="w-3 h-3 rounded-full bg-green-500"></div>

        <span className="text-green-400 font-medium">
          Ready
        </span>
      </div>

    </header>
  );
}

export default Header;