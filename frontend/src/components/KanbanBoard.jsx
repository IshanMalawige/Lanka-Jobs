import { useState } from "react";
import { api } from "../api.js";
import { JobInfo } from "../pages/JobFeed.jsx";

const COLUMNS = [
  { id: "applied", title: "Applied / Processing", statuses: ["applied"], drop: "applied", tone: "border-t-teal" },
  { id: "interview", title: "Interview / Offer", statuses: ["interview", "offer"], drop: "interview", tone: "border-t-amber" },
  { id: "rejected", title: "Rejected", statuses: ["rejected"], drop: "rejected", tone: "border-t-rose" },
];

function Card({ job, patch }) {
  const [open, setOpen] = useState(false);
  const [tracker, setTracker] = useState(null);

  const makePixel = async () => {
    const recipient = prompt("HR email address (optional):") ?? "";
    setTracker(await api.createTracker(job.id, recipient));
  };

  return (
    <article draggable onDragStart={(e) => e.dataTransfer.setData("text/plain", String(job.id))}
      className="bg-white border border-line rounded-md p-3 cursor-grab active:cursor-grabbing">
      <a href={job.url} target="_blank" rel="noreferrer" className="font-medium text-sm hover:underline">{job.title}</a>
      <div className="text-xs text-ink/70 mt-0.5">{job.company || "Company not listed"}</div>
      <div className="flex items-center gap-2 mt-2 text-xs">
        <span className="px-1.5 py-0.5 rounded bg-paper">{job.category}</span>
        {job.status === "offer" && <span className="px-1.5 py-0.5 rounded bg-teal text-white">Offer</span>}
        <button className="ml-auto text-teal hover:underline" onClick={() => setOpen(!open)} aria-expanded={open}>{open ? "Less" : "Details"}</button>
      </div>
      {open && (
        <div className="mt-3 pt-3 border-t border-line space-y-3 text-sm">
          <JobInfo job={job} />
          <label className="block">
            <span className="text-xs text-ink/60">Notes</span>
            <textarea className="mt-1 w-full border border-line rounded p-2 text-sm" rows={3} defaultValue={job.notes}
              onBlur={(e) => e.target.value !== job.notes && patch(job.id, { notes: e.target.value })} />
          </label>
          <div className="flex flex-wrap gap-2">
            {job.status === "interview" && <button className="px-2 py-1 rounded border border-line" onClick={() => patch(job.id, { status: "offer" })}>Mark offer</button>}
            <button className="px-2 py-1 rounded border border-line" onClick={makePixel}>Tracked email snippet</button>
          </div>
          {tracker && (
            <div className="text-xs">
              <p className="mb-1">Paste this at the end of your email body (HTML mode). Opens so far appear when you reload.</p>
              <textarea readOnly className="w-full border border-line rounded p-1 font-mono" rows={3} value={tracker.html_snippet} onFocus={(e) => e.target.select()} />
            </div>
          )}
        </div>
      )}
    </article>
  );
}

export default function KanbanBoard({ jobs, patch }) {
  const [over, setOver] = useState(null);

  const onDrop = (e, col) => {
    e.preventDefault();
    setOver(null);
    const id = Number(e.dataTransfer.getData("text/plain"));
    const job = jobs.find((j) => j.id === id);
    if (job && !col.statuses.includes(job.status)) patch(id, { status: col.drop });
  };

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 items-start">
      {COLUMNS.map((col) => {
        const items = jobs.filter((j) => col.statuses.includes(j.status));
        return (
          <section key={col.id} aria-label={col.title}
            onDragOver={(e) => { e.preventDefault(); setOver(col.id); }} onDragLeave={() => setOver(null)}
            onDrop={(e) => onDrop(e, col)}
            className={`border border-line border-t-4 ${col.tone} rounded-lg p-3 min-h-[200px] ${over === col.id ? "bg-teal/10" : "bg-white/60"}`}>
            <h2 className="font-display font-bold mb-3 flex justify-between">{col.title}<span className="text-ink/50 font-sans font-normal">{items.length}</span></h2>
            <div className="space-y-2">
              {items.map((j) => <Card key={j.id} job={j} patch={patch} />)}
              {items.length === 0 && <p className="text-sm text-ink/50 py-6 text-center">Drag a job here</p>}
            </div>
          </section>
        );
      })}
    </div>
  );
}
