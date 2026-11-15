import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export const CATEGORIES = ["IT", "Interns", "IT Support", "Network", "Systems", "Security", "Other"];

const BLOCK_TAGS = new Set(["address", "article", "blockquote", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ol", "p", "section", "ul"]);

export function cleanJobText(value) {
  let input = String(value || "").trim();
  if (!input) return "";
  if (typeof DOMParser === "undefined") {
    return input.replace(/<[^>]*>/g, " ").replace(/&nbsp;/gi, " ").replace(/\s+/g, " ").trim();
  }

  for (let attempt = 0; attempt < 5; attempt += 1) {
    const inertInput = input
      .replace(/<(script|style|iframe|object|svg|video|audio)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, " ")
      .replace(/<(?:img|embed|source|link|meta|input)\b[^>]*\/?>/gi, " ");
    const doc = new DOMParser().parseFromString(inertInput, "text/html");
    doc.querySelectorAll("script, style, noscript").forEach((node) => node.remove());
    const bodyNodes = [...doc.body.childNodes];
    const hasMarkup = bodyNodes.some((node) => node.nodeType === 1);

    if (!hasMarkup) {
      const decoded = doc.body.textContent || "";
      if (decoded !== input) {
        input = decoded;
        continue;
      }
      return input;
    }

    const readNode = (node) => {
      if (node.nodeType === 3) return node.nodeValue || "";
      if (node.nodeType !== 1) return [...node.childNodes].map(readNode).join("");
      const tag = node.tagName.toLowerCase();
      if (["script", "style", "noscript"].includes(tag)) return "";
      if (tag === "br") return "\n";
      const content = [...node.childNodes].map(readNode).join("");
      if (tag === "li") return `- ${content.trim()}\n`;
      return BLOCK_TAGS.has(tag) ? `\n${content.trim()}\n` : content;
    };

    return bodyNodes.map(readNode).join("")
      .replace(/\u00a0/g, " ")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  return input.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

export function compareSkillMatch(a, b) {
  const aMatch = a.skill_match?.match_percent;
  const bMatch = b.skill_match?.match_percent;
  if (aMatch == null && bMatch != null) return 1;
  if (aMatch != null && bMatch == null) return -1;
  if (aMatch != null && bMatch != null && aMatch !== bMatch) return bMatch - aMatch;

  const dateDifference = Date.parse(b.created_at || "") - Date.parse(a.created_at || "");
  return Number.isFinite(dateDifference) && dateDifference !== 0 ? dateDifference : b.id - a.id;
}

export function SkillMatch({ match }) {
  if (!match || !match.skills_configured) {
    return <p className="text-xs text-ink/60">Upload your CV to see an automatic match.</p>;
  }
  if (match.match_percent === null) {
    return (
      <p className="text-xs text-ink/60">
        {match.estimate_unavailable
          ? "Not enough TopJobs details to estimate a match."
          : "No matching skills were detected in this listing."}
      </p>
    );
  }
  return (
    <div className="text-sm">
      <strong>
        {match.match_percent}% {match.estimated ? "estimated CV match" : match.profile_source === "CV" ? "CV match" : "skill match"}
      </strong>
      {match.estimated && <p className="mt-1 text-xs text-ink/55">Based on the job title; TopJobs did not list required skills.</p>}
      {match.have?.length > 0 && <p className="mt-1 text-xs text-ink/60">Matched: {match.have.join(", ")}</p>}
      {match.missing?.length > 0
        ? <p className="mt-1 text-xs text-ink/60">Missing: {match.missing.join(", ")}</p>
        : <p className="mt-1 text-xs text-ink/60">Your skills cover all detected requirements.</p>}
    </div>
  );
}

function ApplyNowDialog({ job, detectedEmail, onClose }) {
  const [recipient, setRecipient] = useState(detectedEmail);
  const [name, setName] = useState("Ishan Malawige");
  const [contact, setContact] = useState("+94 78 916 3460");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState([
    "Dear Hiring Manager,",
    "",
    `I would like to apply for the position ${job.title}${job.company ? ` at ${job.company}` : ""}. Kindly find my CV attached for your review and consideration. If my qualifications align with your expectations, I would appreciate the opportunity to move forward in the recruitment process.`,
    "",
    "Thank you for your time.",
    "",
    "Kind regards,",
    "Ishan Malawige",
    "Mobile: +94 78 916 3460",
  ].join("\n"));
  const [cvFile, setCvFile] = useState(null);
  const [sendCopy, setSendCopy] = useState(false);
  const [error, setError] = useState("");
  const [opened, setOpened] = useState(false);
  const dialogRef = useRef(null);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    closeButtonRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...(dialogRef.current?.querySelectorAll("button:not(:disabled), input:not(:disabled), textarea:not(:disabled)") || [])];
      if (!focusable.length) return;
      if (event.shiftKey && document.activeElement === focusable[0]) {
        event.preventDefault();
        focusable[focusable.length - 1].focus();
      } else if (!event.shiftKey && document.activeElement === focusable[focusable.length - 1]) {
        event.preventDefault();
        focusable[0].focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown, true);
    return () => document.removeEventListener("keydown", handleKeyDown, true);
  }, [onClose]);

  const submitApplication = (event) => {
    event.preventDefault();
    setError("");
    if (!cvFile) {
      setError("Choose your CV before continuing.");
      return;
    }
    if (cvFile.size > 2 * 1024 * 1024) {
      setError("The CV must be 2 MB or smaller.");
      return;
    }

    const messageWithoutSignature = message.replace(/\nKind regards,\n[\s\S]*$/i, "").trimEnd();
    const applicationMessage = `${messageWithoutSignature}\n\nKind regards,\n${name}\nMobile: ${contact}\nEmail: ${email}`;
    const params = new URLSearchParams({
      subject: `Application for ${job.title}`,
      body: applicationMessage,
    });
    if (sendCopy) params.set("cc", email);
    window.location.href = `mailto:${recipient}?${params.toString()}`;
    setOpened(true);
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/55 p-3 sm:p-5"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="apply-dialog-title"
        className="max-h-[94vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-white px-5 py-4 sm:px-7">
          <div className="min-w-0">
            <h2 id="apply-dialog-title" className="font-display text-xl font-bold text-ink">Apply by email</h2>
            <p className="mt-1 truncate text-sm text-ink/60">{job.title}{job.company ? ` · ${job.company}` : ""}</p>
          </div>
          <button ref={closeButtonRef} type="button" onClick={onClose} className="rounded-lg px-3 py-1 text-xl leading-none text-ink/55 hover:bg-paper" aria-label="Close application form">
            &times;
          </button>
        </header>

        <form onSubmit={submitApplication} className="space-y-5 p-5 sm:p-7">
          <div>
            <label htmlFor="application-recipient" className="mb-1.5 block text-sm font-medium text-ink">Company email <span className="text-rose">*</span></label>
            <input
              id="application-recipient"
              type="email"
              required
              autoComplete="email"
              value={recipient}
              onChange={(event) => setRecipient(event.target.value)}
              className="w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none focus:border-teal focus:ring-2 focus:ring-teal/15"
              placeholder="careers@company.com"
            />
          </div>

          <p className="rounded-lg border border-emerald-300 bg-emerald-50 px-3.5 py-3 text-sm text-emerald-900">
            Your email app will open with the application details. Attach your CV there before sending; browsers cannot attach files through an email link.
          </p>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="application-name" className="mb-1.5 block text-sm font-medium text-ink">Your name <span className="text-rose">*</span></label>
              <input id="application-name" required autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} className="w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none focus:border-teal focus:ring-2 focus:ring-teal/15" />
            </div>
            <div>
              <label htmlFor="application-contact" className="mb-1.5 block text-sm font-medium text-ink">Contact number <span className="text-rose">*</span></label>
              <input id="application-contact" required type="tel" autoComplete="tel" value={contact} onChange={(event) => setContact(event.target.value)} className="w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none focus:border-teal focus:ring-2 focus:ring-teal/15" />
            </div>
            <div>
              <label htmlFor="application-email" className="mb-1.5 block text-sm font-medium text-ink">Your email <span className="text-rose">*</span></label>
              <input id="application-email" required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none focus:border-teal focus:ring-2 focus:ring-teal/15" placeholder="Check your email address" />
            </div>
          </div>

          <div>
            <label htmlFor="application-message" className="mb-1.5 block text-sm font-medium text-ink">Message <span className="text-rose">*</span></label>
            <textarea id="application-message" required rows={7} value={message} onChange={(event) => setMessage(event.target.value)} className="w-full resize-y rounded-lg border border-line px-3 py-2.5 text-sm leading-relaxed outline-none focus:border-teal focus:ring-2 focus:ring-teal/15" />
          </div>

          <div>
            <label htmlFor="application-cv" className="mb-1.5 block text-sm font-medium text-ink">Attach your CV <span className="text-rose">*</span></label>
            <input
              id="application-cv"
              required
              type="file"
              accept=".doc,.docx,.odt,.pdf,.jpg,.jpeg,.png"
              onChange={(event) => {
                const file = event.target.files?.[0] || null;
                setCvFile(file);
                setError("");
              }}
              className="block w-full rounded-lg border border-line text-sm file:mr-3 file:border-0 file:bg-paper file:px-3 file:py-2.5 file:text-sm file:font-semibold file:text-ink"
            />
            <p className="mt-1.5 text-xs text-ink/55">DOC, DOCX, ODT, PDF, JPG or PNG · Maximum 2 MB. You will need to attach it again in your email app.</p>
            {cvFile && <p className="mt-1 text-xs text-ink/70">Selected: {cvFile.name}</p>}
          </div>

          <label className="flex items-center gap-2 text-sm text-ink/75">
            <input type="checkbox" checked={sendCopy} onChange={(event) => setSendCopy(event.target.checked)} className="h-4 w-4 accent-teal" />
            Send me a copy of my application email
          </label>

          {error && <p className="text-sm text-rose" role="alert">{error}</p>}
          {opened && <p className="text-sm text-emerald-700" role="status">Your email app should open with this application. Attach the selected CV and send it there.</p>}

          <div className="flex flex-wrap justify-end gap-2 border-t border-line pt-4">
            <button type="button" onClick={onClose} className="rounded-lg border border-line px-4 py-2.5 text-sm font-semibold text-ink/70 hover:bg-paper">Close</button>
            <button type="submit" className="rounded-lg bg-teal px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-dark">Send application</button>
          </div>
        </form>
      </section>
    </div>,
    document.body,
  );
}

export function JobInfo({ job }) {
  const [applyOpen, setApplyOpen] = useState(false);
  const description = cleanJobText(job.description);
  const requirements = cleanJobText(job.requirements);
  const howToApply = cleanJobText(job.how_to_apply);
  const hasDetails = description || requirements || howToApply || job.poster_image_url;
  const applicationEmail = `${job.how_to_apply || ""}\n${job.description || ""}\n${job.requirements || ""}`
    .match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i)?.[0];
  const applicationUrl = job.how_to_apply.match(/https?:\/\/[^\s<>"']+/i)?.[0].replace(/[),.;]+$/, "");
  const isITPro = job.source === "itpro";
  const isLinkedIn = job.source === "linkedin";
  const linkedInEmailInstructions = isLinkedIn && /(?:send|email|e-mail|mail|submit|forward).{0,100}\b(?:cv|resume|application|cover letter)\b|\b(?:cv|resume|application|cover letter)\b.{0,100}(?:send|email|e-mail|mail|submit|forward)/i.test(`${howToApply}\n${description}`);
  const externalApplyUrl = isITPro
    ? job.url
    : isLinkedIn ? (linkedInEmailInstructions ? "" : job.url)
      : job.source === "topjobs" ? "" : applicationUrl;
  const applyButtonClass = "mt-3 inline-flex rounded-lg bg-teal px-4 py-2 font-semibold text-white transition hover:bg-teal-dark";
  return (
    <div className="space-y-3 text-sm">
      {description && <section>
        <h3 className="font-semibold">Job description</h3>
        <p className="mt-1 whitespace-pre-line text-ink/80">{description}</p>
      </section>}
      {job.poster_image_url && <img
        src={job.poster_image_url}
        alt={`${job.title} job advertisement`}
        loading="lazy"
        className="max-h-[32rem] w-full rounded-md border border-line bg-white object-contain"
        onError={(event) => event.currentTarget.remove()}
      />}
      {requirements && <section>
        <h3 className="font-semibold">Requirements</h3>
        <p className="mt-1 whitespace-pre-line text-ink/80">{requirements}</p>
      </section>}
      {(howToApply || job.source === "topjobs" || isITPro || isLinkedIn) && <section>
        <h3 className="font-semibold">How to apply</h3>
        <p className="mt-1 whitespace-pre-line text-ink/80">
          {isITPro && !howToApply
            ? "Continue to the ITPro listing to apply for this job."
            : job.source === "topjobs" && /online cv/i.test(howToApply) && !applicationEmail
            ? "No direct employer email was listed. You can prepare an email application here if you have the employer's address."
            : howToApply}
        </p>
        {externalApplyUrl && (isITPro || (isLinkedIn && !linkedInEmailInstructions) || !applicationEmail)
          ? <a href={externalApplyUrl} target="_blank" rel="noreferrer" className={applyButtonClass}>{isITPro ? "Apply on ITPro" : isLinkedIn ? "Apply on LinkedIn" : "Apply Now"}</a>
          : <button type="button" onClick={() => setApplyOpen(true)} className={applyButtonClass}>Apply Now</button>}
      </section>}
      {!howToApply && applicationEmail && <section>
        <h3 className="font-semibold">Apply by email</h3>
        <div className="mt-2">
          <button type="button" onClick={() => setApplyOpen(true)} className="inline-flex rounded-lg bg-teal px-4 py-2 font-semibold text-white transition hover:bg-teal-dark">
            Apply Now
          </button>
        </div>
      </section>}
      {!hasDetails && <p className="text-ink/60">The listing did not provide a description or application details.</p>}
      {applyOpen && <ApplyNowDialog job={job} detectedEmail={applicationEmail || ""} onClose={() => setApplyOpen(false)} />}
    </div>
  );
}

export default function JobFeed({ jobs, patch }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [source, setSource] = useState("");
  const [sort, setSort] = useState("new");

  const sources = useMemo(() => [...new Set(
    jobs.map((j) => j.source).filter((item) => !["careers", "extension", "manual"].includes(item)),
  )].sort(), [jobs]);
  const shown = useMemo(() => {
    const t = q.toLowerCase();
    const list = jobs.filter((j) =>
      (!cat || j.category === cat) && (!source || j.source === source) &&
      (!t || `${j.title} ${j.company}`.toLowerCase().includes(t)));
    if (sort === "match") return [...list].sort(compareSkillMatch);
    return sort === "company" ? [...list].sort((a, b) => a.company.localeCompare(b.company)) : list;
  }, [jobs, q, cat, source, sort]);

  const field = "px-3 py-2 rounded-md border border-line bg-white text-sm";
  return (
    <section>
      <div className="flex flex-wrap gap-2 mb-5">
        <input className={`${field} flex-1 min-w-[220px]`} placeholder="Search title or company" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className={field} value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Category">
          <option value="">All roles</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className={field} value={source} onChange={(e) => setSource(e.target.value)} aria-label="Source">
          <option value="">All sources</option><option value="careers">Banking</option>
          {sources.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className={field} value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
          <option value="new">Newest first</option><option value="company">Company A–Z</option>
          <option value="match">Match % (high to low)</option>
        </select>
      </div>
      {shown.length === 0 && (
        <p className="py-16 text-center text-ink/60">No jobs match. Click “Find new jobs” or save one with the browser extension.</p>
      )}
      <ul className="divide-y divide-line bg-white border border-line rounded-lg">
        {shown.map((j) => (
          <li key={j.id} className="p-4 flex flex-wrap gap-4 items-start">
            <div className="flex-1 min-w-[260px]">
              <span className="font-medium">{j.title}</span>
              <div className="text-sm text-ink/70">{j.company || "Company not listed"} · {j.category} · {j.source}</div>
              <div className="mt-1"><SkillMatch match={j.skill_match} /></div>
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-teal hover:underline">Job description, requirements &amp; how to apply</summary>
                <div className="mt-3 rounded-md bg-paper p-3"><JobInfo job={j} /></div>
              </details>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="px-2 py-1 rounded bg-paper">{j.status}</span>
              {j.status === "saved" ? (
                <button className="px-3 py-1.5 rounded-md border border-line hover:bg-paper" onClick={() => patch(j.id, { status: "viewed" })}>Mark viewed</button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
