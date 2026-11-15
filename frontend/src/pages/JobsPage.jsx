import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { CATEGORIES, compareSkillMatch } from "./JobFeed.jsx";
import { RecentCard } from "./Dashboard.jsx";

const PAGE_SIZE = 24;
const FIELD_CLASS = "min-w-0 rounded-md border border-line bg-white px-3 py-2.5 text-sm";
const EXPERIENCE_FILTERS = [
  { value: "0-1", label: "0–1 years" },
  { value: "2-3", label: "2–3 years" },
  { value: "4-5", label: "4–5 years" },
  { value: "6+", label: "6+ years" },
  { value: "unspecified", label: "Not specified" },
];

const BANK_LOGO_OVERRIDES = {
  "Hatton National Bank (HNB)": "https://www.hnb.lk/logo192.png",
  "Commercial Bank of Ceylon": "https://upload.wikimedia.org/wikipedia/commons/f/fb/Commercial_Bank_logo.svg",
};
const SOURCE_LOGO_DOMAINS = {
  itpro: "itpro.lk",
  linkedin: "linkedin.com",
  topjobs: "topjobs.lk",
  xpress: "xpress.jobs",
};

function SourceLogo({ source }) {
  const [logoFailed, setLogoFailed] = useState(false);
  const domain = SOURCE_LOGO_DOMAINS[source];
  if (!domain) return null;

  return (
    <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-white">
      {logoFailed ? (
        <span className="text-[9px] font-bold uppercase text-ink/70" aria-hidden="true">{source.slice(0, 2)}</span>
      ) : (
        <img
          src={`https://www.google.com/s2/favicons?domain=${domain}&sz=64`}
          alt=""
          aria-hidden="true"
          loading="lazy"
          referrerPolicy="no-referrer"
          className="h-4 w-4 object-contain"
          onError={() => setLogoFailed(true)}
        />
      )}
    </span>
  );
}

function BankCareerCard({ item }) {
  const [logoFailed, setLogoFailed] = useState(false);
  const logoDomain = new URL(item.url).hostname.replace(/^(?:www|careers)\./i, "");
  const initials = item.company
    .split(/\s+/)
    .filter((part) => !["of", "the", "(boc)", "(nsb)", "(ndb)", "(ntb)", "(cbsl)"].includes(part.toLowerCase()))
    .slice(0, 2)
    .map((part) => part.replace(/[^a-z]/gi, "").slice(0, 1).toUpperCase())
    .join("");
  const logoUrl = BANK_LOGO_OVERRIDES[item.company]
    || `https://www.google.com/s2/favicons?domain=${encodeURIComponent(logoDomain)}&sz=128`;

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noreferrer"
      className="group min-h-36 rounded-2xl border border-line bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-teal/50 hover:shadow-md sm:p-6"
    >
      <span className="flex items-start gap-4">
        <span className="relative flex h-14 w-14 flex-shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-line/70 bg-gradient-to-br from-teal/10 to-indigo-100 text-sm font-bold text-teal">
          <span aria-hidden="true">{initials}</span>
          {!logoFailed && (
            <img
              src={logoUrl}
              alt=""
              loading="lazy"
              referrerPolicy="no-referrer"
              className="absolute inset-0 h-full w-full bg-white object-contain p-2"
              onError={() => setLogoFailed(true)}
            />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-ink">{item.company}</span>
          <span className="mt-1 block text-xs text-ink/55">{item.group} · Official careers</span>
        </span>
        <svg viewBox="0 0 20 20" className="mt-0.5 h-4 w-4 flex-shrink-0 text-ink/35 transition group-hover:text-teal" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M11 3h6v6M17 3 9 11M15 11v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
        </svg>
      </span>
    </a>
  );
}

export default function JobsPage({ jobs = [], patch }) {
  const [cards, setCards] = useState([]);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [level, setLevel] = useState("");
  const [experience, setExperience] = useState("");
  const [sort, setSort] = useState("new");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [totalJobs, setTotalJobs] = useState(null);
  const [error, setError] = useState("");
  const [bankingSources, setBankingSources] = useState([]);
  const [bankingSourcesLoading, setBankingSourcesLoading] = useState(true);
  const [bankingSourcesError, setBankingSourcesError] = useState("");
  const sentinelRef = useRef(null);
  const offsetRef = useRef(0);
  const requestRef = useRef(0);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const headRequestRef = useRef(0);
  const bankingSelected = source === "banking";

  useEffect(() => {
    let active = true;
    api.bankingSources()
      .then((sources) => { if (active) setBankingSources(sources); })
      .catch((err) => { if (active) setBankingSourcesError(err.message || "Bank career pages could not be loaded."); })
      .finally(() => { if (active) setBankingSourcesLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchPage = useCallback(async (reset = false) => {
    if (source === "banking") {
      if (reset) requestRef.current += 1;
      offsetRef.current = 0;
      loadingRef.current = false;
      hasMoreRef.current = false;
      setCards([]);
      setHasMore(false);
      setTotalJobs(0);
      setLoading(false);
      setError("");
      return;
    }
    if (!reset && (loadingRef.current || !hasMoreRef.current)) return;
    if (reset) {
      requestRef.current += 1;
      offsetRef.current = 0;
      loadingRef.current = false;
      hasMoreRef.current = true;
      setTotalJobs(null);
      setHasMore(true);
    }

    const requestId = requestRef.current;
    const offset = reset ? 0 : offsetRef.current;
    loadingRef.current = true;
    setLoading(true);
    setError("");

    try {
      const filters = { q: query, category, source, level, experience };
      const pageRequest = api.jobs({ ...filters, sort, limit: PAGE_SIZE, offset });
      const [page, count] = reset
        ? await Promise.all([pageRequest, api.jobCount(filters)])
        : [await pageRequest, null];
      if (requestRef.current !== requestId) return;
      setCards((current) => reset ? page : [...current, ...page]);
      if (count) setTotalJobs(count.total);
      offsetRef.current = offset + page.length;
      hasMoreRef.current = page.length === PAGE_SIZE;
      setHasMore(hasMoreRef.current);
    } catch (err) {
      if (requestRef.current === requestId) setError(err.message || "Could not load jobs.");
    } finally {
      if (requestRef.current === requestId) {
        loadingRef.current = false;
        setLoading(false);
      }
    }
  }, [query, category, source, level, experience, sort]);

  useEffect(() => {
    setCards([]);
    setError("");
    fetchPage(true);
  }, [fetchPage]);

  const refreshHead = useCallback(async () => {
    const requestId = ++headRequestRef.current;
    if (source === "banking") {
      setCards([]);
      return;
    }
    try {
      const filters = { q: query, category, source, level, experience };
      const [head, count] = await Promise.all([
        api.jobs({ ...filters, sort, limit: PAGE_SIZE, offset: 0 }),
        api.jobCount(filters),
      ]);
      if (headRequestRef.current !== requestId) return;
      setTotalJobs(count.total);
      setCards((current) => {
        const byId = new Map(current.map((job) => [job.id, job]));
        for (const job of head) byId.set(job.id, { ...byId.get(job.id), ...job });
        const merged = [...byId.values()];
        if (sort === "match") return merged.sort(compareSkillMatch);
        if (sort === "company") {
          return merged.sort((a, b) => (a.company || "").localeCompare(b.company || "") || b.id - a.id);
        }
        return merged.sort((a, b) => {
          const dateDifference = Date.parse(b.created_at || "") - Date.parse(a.created_at || "");
          return Number.isFinite(dateDifference) && dateDifference !== 0 ? dateDifference : b.id - a.id;
        });
      });
    } catch (err) {
      if (headRequestRef.current === requestId) console.error("Could not refresh job listings:", err);
    }
  }, [query, category, source, level, experience, sort]);

  useEffect(() => {
    refreshHead();
    const timer = setInterval(refreshHead, 60_000);
    return () => clearInterval(timer);
  }, [refreshHead]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || error || typeof IntersectionObserver === "undefined") return undefined;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) fetchPage(false);
    }, { rootMargin: "300px 0px" });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [fetchPage, hasMore, error, loading]);

  const sources = useMemo(() => [...new Set([
    "itpro", "linkedin", "topjobs", "xpress", ...jobs.map((job) => job.source),
  ].filter((item) => item && !["careers", "extension", "manual"].includes(item)))].sort(), [jobs]);

  const updateJob = useCallback(async (id, changes) => {
    const original = cards.find((job) => job.id === id);
    setCards((current) => current.map((job) => job.id === id ? { ...job, ...changes } : job));
    const updated = await patch(id, changes);
    if (updated === false && original) {
      setCards((current) => current.map((job) => job.id === id ? original : job));
      return false;
    }
    return updated;
  }, [cards, patch]);

  return (
    <div className="space-y-6">
      <section aria-labelledby="job-listings-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 id="job-listings-heading" className="font-display text-2xl font-bold text-ink">
              {bankingSelected ? "Bank career pages" : "Job listings"}
            </h1>
            <p className="mt-0.5 text-sm text-ink/60">
              {bankingSelected
                ? `${bankingSources.length} official bank career links`
                : totalJobs === null
                  ? `Showing ${cards.length} jobs`
                  : `Showing ${cards.length} of ${totalJobs} jobs`}
            </p>
          </div>
        </div>

        <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="Filter jobs by source">
          <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-ink/50">Sources</span>
          {[
            { value: "", label: "All sources" },
            { value: "banking", label: "Banking" },
            ...sources.map((item) => ({ value: item, label: item })),
          ].map((item) => (
            <button
              key={item.value || "all"}
              type="button"
              aria-pressed={source === item.value}
              onClick={() => setSource(item.value)}
              className={`rounded-full border px-3.5 py-1.5 text-sm font-medium capitalize transition ${
                source === item.value
                  ? "border-ink bg-ink text-white shadow-sm"
                  : "border-line bg-white text-ink/70 hover:border-teal/50 hover:bg-teal/5 hover:text-teal"
              }`}
            >
              <span className="inline-flex items-center gap-2">
                <SourceLogo source={item.value} />
                {item.label}
              </span>
            </button>
          ))}
        </div>

        {!bankingSelected && <div className="mb-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_auto_auto_auto_auto]">
          <input
            className={`${FIELD_CLASS} sm:col-span-2 xl:col-span-1`}
            placeholder="Search title or company"
            aria-label="Search title or company"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select className={FIELD_CLASS} value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter by role">
            <option value="">All roles</option>
            {CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select className={FIELD_CLASS} value={level} onChange={(event) => setLevel(event.target.value)} aria-label="Filter by position level">
            <option value="">All levels</option>
            <option value="junior">Junior</option>
            <option value="senior">Senior</option>
          </select>
          <select className={FIELD_CLASS} value={experience} onChange={(event) => setExperience(event.target.value)} aria-label="Filter by required experience">
            <option value="">Any experience</option>
            {EXPERIENCE_FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <select className={FIELD_CLASS} value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort jobs">
            <option value="new">Newest first</option>
            <option value="company">Company A-Z</option>
            <option value="match">Match % (high to low)</option>
          </select>
        </div>}

        {!bankingSelected && error && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rose/30 bg-rose/5 p-3 text-sm text-rose" role="alert">
            <span>{error}</span>
            <button className="font-semibold underline" onClick={() => fetchPage(cards.length === 0)}>Try again</button>
          </div>
        )}

        {bankingSelected && (
          <section aria-labelledby="bank-careers-heading">
            <div className="mb-4">
              <h2 id="bank-careers-heading" className="font-display text-lg font-bold text-ink">Choose a bank to view its career page</h2>
              <p className="mt-1 text-sm text-ink/60">These are official career pages; selecting a card opens that bank's site.</p>
            </div>
            {bankingSourcesError ? (
              <p className="text-sm text-rose" role="alert">{bankingSourcesError}</p>
            ) : bankingSourcesLoading ? (
              <p className="text-sm text-ink/55" role="status">Loading bank career pages...</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {bankingSources.map((item) => (
                  <BankCareerCard key={item.company} item={item} />
                ))}
              </div>
            )}
          </section>
        )}

        {!bankingSelected && cards.length === 0 && !loading && !error ? (
          <div className="rounded-xl border border-line p-10 text-center">
            <p className="text-sm text-ink/50">{query || category || source || level || experience ? "No jobs match these filters." : "No jobs yet. New matches will appear automatically after a search."}</p>
          </div>
        ) : !bankingSelected ? (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              {cards.map((job) => <RecentCard key={job.id} job={job} patch={updateJob} />)}
            </div>
            {hasMore && !error && <div ref={sentinelRef} className="h-8" aria-hidden="true" />}
            {loading && <p className="py-5 text-center text-sm text-ink/60" role="status">Loading jobs...</p>}
            {!hasMore && cards.length > 0 && <p className="py-5 text-center text-sm text-ink/50">You are all caught up.</p>}
          </>
        ) : null}
      </section>
    </div>
  );
}
