import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api.js";
import { cleanJobText, JobInfo, SkillMatch } from "./JobFeed.jsx";

const COLORS = {
  saved: { card: "bg-blue-50", text: "text-blue-600", border: "border-blue-200" },
  viewed: { card: "bg-gray-50", text: "text-gray-600", border: "border-gray-200" },
  applied: { card: "bg-teal-50", text: "text-teal-600", border: "border-teal-200" },
  interview: { card: "bg-amber-50", text: "text-amber-600", border: "border-amber-200" },
  offer: { card: "bg-emerald-50", text: "text-emerald-600", border: "border-emerald-200" },
  rejected: { card: "bg-rose-50", text: "text-rose-600", border: "border-rose-200" },
};

const STATS = [
  { key: "total", label: "Total jobs", caption: "Across all your sources", color: "text-indigo-600 bg-indigo-50" },
  { key: "saved", label: "Saved", caption: "Ready to review", color: "text-blue-600 bg-blue-50" },
  { key: "viewed", label: "Viewed", caption: "Already explored", color: "text-gray-600 bg-gray-100" },
  { key: "applied", label: "Applied", caption: "Applications sent", color: "text-teal bg-teal/10" },
];

function StatCard({ stat, totals }) {
  return (
    <article className="group rounded-2xl border border-line/70 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-md sm:p-6 lg:p-7">
      <div className="flex items-center justify-between gap-3">
        <p className="text-base font-semibold text-ink/65">{stat.label}</p>
        <span className={`flex h-12 w-12 items-center justify-center rounded-xl ${stat.color}`} aria-hidden="true">
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            {stat.key === "total" && <><rect x="4" y="7" width="16" height="13" rx="2" /><path d="M9 7V5h6v2M4 12h16M10 12v2h4v-2" /></>}
            {stat.key === "saved" && <path d="M6 4.8A1.8 1.8 0 0 1 7.8 3h8.4A1.8 1.8 0 0 1 18 4.8V21l-6-3.5L6 21V4.8Z" />}
            {stat.key === "viewed" && <><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" /><circle cx="12" cy="12" r="2.5" /></>}
            {stat.key === "applied" && <><path d="m21 3-7.2 18-3.9-7.9L2 9.2 21 3Z" /><path d="M9.9 13.1 15 8" /></>}
          </svg>
        </span>
      </div>
      <p className="mt-6 font-display text-4xl font-bold tracking-tight text-ink">{totals[stat.key]}</p>
      <p className="mt-2 text-sm text-ink/50">{stat.caption}</p>
    </article>
  );
}

function JobDetailsDialog({ job, onClose, onDetailsUpdated }) {
  const closeButtonRef = useRef(null);
  const [detailsJob, setDetailsJob] = useState(job);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState("");

  const loadDetails = useCallback(async () => {
    if (job.source !== "topjobs" && job.poster_image_url) return;
    setDetailsLoading(true);
    setDetailsError("");
    try {
      const emailAvailable = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(
        `${job.how_to_apply || ""}\n${job.description || ""}`,
      );
      const updated = await api.refreshOneJobDetails(
        job.id,
        !job.poster_image_url || (job.source === "topjobs" && !emailAvailable),
      );
      setDetailsJob((current) => ({ ...current, ...updated }));
      onDetailsUpdated?.(updated);
    } catch (error) {
      setDetailsError(error.message || "Could not fetch the latest job details or poster image.");
    } finally {
      setDetailsLoading(false);
    }
  }, [job.id, job.source, job.poster_image_url, onDetailsUpdated]);

  useEffect(() => {
    setDetailsJob(job);
    loadDetails();
  }, [job, loadDetails]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = [...document.querySelectorAll(
        `#job-dialog-${job.id} button:not(:disabled), #job-dialog-${job.id} a[href]`,
      )];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus?.();
    };
  }, [job.id, onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        id={`job-dialog-${job.id}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`job-dialog-title-${job.id}`}
        className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-line p-5">
          <div className="min-w-0">
            <h2 id={`job-dialog-title-${job.id}`} className="font-display text-xl font-bold text-ink">
              {job.title}
            </h2>
            <p className="mt-1 text-sm text-ink/60">{job.company || "Company not listed"}</p>
            {job.source !== "topjobs" && (
              <a href={job.url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm font-semibold text-teal hover:underline">
                Open original job posting
              </a>
            )}
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            className="flex-shrink-0 rounded-md px-3 py-1 text-xl leading-none text-ink/60 hover:bg-paper hover:text-ink"
            aria-label="Close job description"
            onClick={onClose}
          >
            &times;
          </button>
        </header>
        <div className="overflow-y-auto p-5">
          {detailsLoading && <p className="mb-3 text-sm text-ink/60" role="status">Fetching job details and poster image…</p>}
          {detailsError && (
            <div className="mb-3 space-y-2" role="alert">
              <p className="text-sm text-rose">{detailsError}</p>
              <button type="button" className="text-sm font-semibold text-teal hover:underline" onClick={loadDetails}>
                Try again
              </button>
            </div>
          )}
          <JobInfo job={detailsJob} />
        </div>
      </section>
    </div>,
    document.body,
  );
}

export function RecentCard({ job, patch }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [cardDescription, setCardDescription] = useState(job.description);
  const closeDetails = useCallback(() => setDetailsOpen(false), []);
  const updateCardDetails = useCallback((updated) => {
    if (updated.description) setCardDescription(updated.description);
  }, []);
  useEffect(() => setCardDescription(job.description), [job.description]);
  const statusColors = COLORS[job.status] || {};
  const description = cleanJobText(cardDescription);
  const progress = { applied: 50, interview: 70, offer: 100 }[job.status];

  return (
    <>
    <article className="overflow-hidden rounded-2xl border border-line bg-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg">
      <div className="p-5">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal/15 to-indigo-100 text-lg font-bold text-teal">
            {(job.company || job.title || "J").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <button
                  type="button"
                  className="line-clamp-2 text-left font-display text-base font-bold leading-snug text-ink hover:text-teal hover:underline"
                  aria-haspopup="dialog"
                  aria-expanded={detailsOpen}
                  onClick={() => setDetailsOpen(true)}
                >
                  {job.title}
                </button>
                <p className="mt-1 truncate text-sm text-ink/60">{job.company || "Company not listed"}</p>
              </div>
              <span className={`flex-shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${statusColors.card || "bg-paper"} ${statusColors.text || "text-ink/60"}`}>
                {job.status}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-paper px-2.5 py-1 text-xs text-ink/70">{job.category || "Uncategorized"}</span>
              <span className="rounded-full bg-paper px-2.5 py-1 text-xs text-ink/60">{job.source || "Unknown source"}</span>
            </div>
          </div>
        </div>

        <div className="mt-4 min-h-[3.75rem]">
          {description ? (
            <p className="line-clamp-3 whitespace-pre-line text-sm leading-relaxed text-ink/70">{description}</p>
          ) : (
            <p className="text-sm italic text-ink/45">Description not available yet.</p>
          )}
        </div>

        {progress !== undefined && (
          <div className="mt-4">
            <div className="mb-1.5 flex justify-between text-xs text-ink/60">
              <span>Application progress</span><span>{progress}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className={`h-full rounded-full ${job.status === "offer" ? "bg-emerald-500" : job.status === "interview" ? "bg-amber-500" : "bg-teal-500"}`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <button
            type="button"
            className="text-sm font-semibold text-teal hover:underline"
            aria-expanded={detailsOpen}
            aria-haspopup="dialog"
            onClick={() => setDetailsOpen(true)}
          >
            View job description
          </button>
          <div className="flex items-center gap-3">
            {job.status === "saved" && (
              <button
                type="button"
                className="rounded-lg border border-line px-3 py-2 text-xs font-semibold text-ink transition hover:bg-paper"
                onClick={() => patch(job.id, { status: "viewed" })}
              >
                Mark viewed
              </button>
            )}
            <SkillMatch match={job.skill_match} />
          </div>
        </div>

      </div>
    </article>
    {detailsOpen && <JobDetailsDialog job={job} onClose={closeDetails} onDetailsUpdated={updateCardDetails} />}
    </>
  );
}

export default function Dashboard({ jobs = [], onNavigate }) {
  const [summaryStats, setSummaryStats] = useState(null);
  const [cvProfile, setCvProfile] = useState(null);
  const [cvMessage, setCvMessage] = useState("");
  const [cvUploading, setCvUploading] = useState(false);

  useEffect(() => {
    api.cvProfile().then(setCvProfile).catch((err) => setCvMessage(err.message || "Could not load CV profile."));
  }, []);

  useEffect(() => {
    let active = true;
    const refreshStats = () => api.stats()
      .then((stats) => { if (active) setSummaryStats(stats); })
      .catch((err) => { if (active) console.error("Could not refresh dashboard stats:", err); });
    refreshStats();
    const timer = setInterval(refreshStats, 60_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const totals = useMemo(() => {
    const counts = summaryStats || jobs.reduce((result, job) => {
      result[job.status] = (result[job.status] || 0) + 1;
      return result;
    }, {});
    return {
      total: ["saved", "viewed", "applied", "interview", "offer", "rejected"].reduce((sum, key) => sum + (counts[key] || 0), 0),
      saved: counts.saved || 0,
      viewed: counts.viewed || 0,
      applied: counts.applied || 0,
    };
  }, [summaryStats, jobs]);

  const uploadCv = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setCvMessage("Choose a PDF CV.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setCvMessage("The CV must be 10 MB or smaller.");
      return;
    }

    setCvUploading(true);
    setCvMessage("Reading your CV locally...");
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(new Error("Could not read the selected PDF."));
        reader.readAsDataURL(file);
      });
      const contentBase64 = dataUrl.split(",", 2)[1];
      const profile = await api.uploadCv({ filename: file.name, content_base64: contentBase64 });
      setCvProfile(profile);
      api.stats()
        .then(setSummaryStats)
        .catch((err) => console.error("Could not refresh dashboard stats:", err));
      setCvMessage(`CV added. ${profile.skills.length} skills will be matched automatically.`);
    } catch (err) {
      setCvMessage(err.message || "Could not add this CV.");
    } finally {
      setCvUploading(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="relative isolate overflow-hidden rounded-3xl bg-gradient-to-br from-ink via-[#1a3557] to-teal-dark px-6 py-7 text-white shadow-xl sm:px-8 sm:py-9 lg:px-10 lg:py-10">
        <div className="pointer-events-none absolute -right-20 -top-28 h-80 w-80 rounded-full border-[36px] border-white/[0.04]" />
        <div className="pointer-events-none absolute -bottom-36 right-[28%] h-72 w-72 rounded-full bg-teal/20 blur-3xl" />
        <div className="relative grid items-center gap-8 lg:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)] lg:gap-12">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.08] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-100">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />
              Your career workspace
            </p>
            <h1 className="mt-5 max-w-2xl font-display text-3xl font-bold leading-tight tracking-tight sm:text-4xl lg:text-5xl">
              Make your next career move <span className="text-teal-200">with confidence.</span>
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-6 text-white/70 sm:text-base">
              Keep your opportunities organized, track your progress, and find roles that fit your skills.
            </p>
            <button
              type="button"
              onClick={() => onNavigate("jobs")}
              className="mt-7 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-ink shadow-lg transition hover:-translate-y-0.5 hover:bg-teal-50"
            >
              Explore jobs
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3.5 10h13M10 3.5l6.5 6.5-6.5 6.5" />
              </svg>
            </button>
          </div>

          <aside className="rounded-2xl border border-white/15 bg-white/[0.09] p-5 shadow-lg backdrop-blur-md sm:p-6" aria-labelledby="cv-profile-heading">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-white/55">Personalize your search</p>
                <h2 id="cv-profile-heading" className="mt-1 font-display text-lg font-semibold">CV matching profile</h2>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${cvProfile?.uploaded ? "bg-emerald-300/15 text-emerald-100" : "bg-white/10 text-white/65"}`}>
                {cvProfile?.uploaded ? "Active" : "Not set up"}
              </span>
            </div>
            <div className="mt-5 flex items-end gap-3">
              <p className="font-display text-4xl font-bold tracking-tight">{cvProfile?.uploaded ? cvProfile.skills?.length || 0 : "—"}</p>
              <p className="pb-1 text-sm text-white/65">{cvProfile?.uploaded ? "skills detected from your CV" : "Upload a CV to match jobs to your skills"}</p>
            </div>
            <label className={`mt-5 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-sm font-semibold transition hover:bg-white/15 ${cvUploading ? "pointer-events-none opacity-60" : ""}`}>
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M10 13V3m0 0L6.5 6.5M10 3l3.5 3.5M4 12.5v3A1.5 1.5 0 0 0 5.5 17h9a1.5 1.5 0 0 0 1.5-1.5v-3" />
              </svg>
              <input className="sr-only" type="file" accept="application/pdf,.pdf" onChange={uploadCv} disabled={cvUploading} />
              {cvUploading ? "Reading your CV..." : cvProfile?.uploaded ? "Replace CV" : "Upload your CV"}
            </label>
            <p className="mt-3 text-center text-xs leading-5 text-white/50">PDF only · Up to 10 MB · Only detected skills are kept</p>
            {cvMessage && <p className="mt-3 rounded-lg bg-white/10 px-3 py-2 text-xs leading-5 text-white/80" role="status">{cvMessage}</p>}
          </aside>
        </div>
      </section>

      <section aria-labelledby="dashboard-stats-heading">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Your progress</p>
            <h2 id="dashboard-stats-heading" className="mt-1 font-display text-xl font-bold text-ink sm:text-2xl">Job search overview</h2>
          </div>
          <p className="text-xs text-ink/50">Counts update automatically as your applications change</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5 lg:grid-cols-4">
          {STATS.map((stat) => <StatCard key={stat.key} stat={stat} totals={totals} />)}
        </div>
      </section>
    </div>
  );
}
