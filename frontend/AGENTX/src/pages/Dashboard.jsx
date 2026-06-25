import Header from "../components/Header";
import InputPanel from "../components/InputPanel";
import Sidebar from "../components/Sidebar";
import CodePanel from "../components/CodePanel";
import AnalysisPanel from "../components/AnalysisPanel";
import LogPanel from "../components/LogPanel";

function Dashboard() {
  return (
    <div className="min-h-screen bg-slate-900 text-white">

      <Header />

      <InputPanel />

      <div className="grid grid-cols-12 gap-4 p-4">

        <div className="col-span-2">
          <Sidebar />
        </div>

        <div className="col-span-7">
          <CodePanel />
        </div>

        <div className="col-span-3">
          <AnalysisPanel />
        </div>

      </div>

      <LogPanel />

    </div>
  );
}

export default Dashboard;