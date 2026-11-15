import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import KanbanBoard from "./components/KanbanBoard.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import JobsPage from "./pages/JobsPage.jsx";

export default function App() {
  const [view, setView] = useState("dashboard");
  const [jobs, setJobs] = useState([]);

  const load = useCallback(() => api.jobs({ limit: 500, include_match: false }).then(setJobs).catch((error) => {
    console.error("Could not load jobs:", error);
  }), []);
  useEffect(() => { load(); }, [load]);

  const patch = async (id, changes) => {
    setJobs((current) => current.map((job) => job.id === id ? { ...job, ...changes } : job));
    try {
      await api.update(id, changes);
      return true;
    } catch (error) {
      console.error("Could not update job:", error);
      load();
      return false;
    }
  };

  const tab = (id, label) => (
    <button
      onClick={() => setView(id)}
      aria-pressed={view === id}
      className={`rounded-md px-4 py-2 text-sm font-medium ${view === id ? "bg-ink text-white" : "text-ink hover:bg-line"}`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-white/90 shadow-sm backdrop-blur-md">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-3 px-5 py-3">
          <button className="mr-4 inline-flex items-center gap-2.5 rounded-lg font-display text-xl font-bold tracking-tight text-ink" onClick={() => setView("dashboard")} aria-label="LankaJobs home">
            <img src="/lankajobs-logo.svg" alt="" className="h-10 w-10" />
            <span>Lanka<span className="text-teal">Jobs</span></span>
          </button>
          <nav className="flex gap-1">
            {tab("jobs", "Jobs")}
            {tab("board", "Applications")}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-5 py-6">
        {view === "dashboard"
          ? <Dashboard jobs={jobs} onNavigate={setView} />
          : view === "jobs"
            ? <JobsPage jobs={jobs} patch={patch} />
            : <KanbanBoard jobs={jobs} patch={patch} />}
      </main>
    </div>
  );
}
