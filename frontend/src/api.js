const API_BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const apiUrl = (path) => `${API_BASE_URL}${path}`;

const j = async (res) => {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
};
const send = (method, url, body) =>
  fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined }).then(j);

export const api = {
  jobs: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
    return fetch(apiUrl(`/api/jobs?${qs}`)).then(j);
  },
  jobCount: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
    return fetch(apiUrl(`/api/jobs/count?${qs}`)).then(j);
  },
  stats: () => fetch(apiUrl("/api/stats")).then(j),
  bankingSources: () => fetch(apiUrl("/api/banking/sources")).then(j),
  cvProfile: () => fetch(apiUrl("/api/cv")).then(j),
  uploadCv: (payload) => send("PUT", apiUrl("/api/cv"), payload),
  update: (id, patch) => send("PATCH", apiUrl(`/api/jobs/${id}`), patch),
  remove: (id) => fetch(apiUrl(`/api/jobs/${id}`), { method: "DELETE" }).then(j),
  skillGap: (id) => fetch(apiUrl(`/api/jobs/${id}/skill-gap`)).then(j),
  refreshOneJobDetails: (id, force = false) => send("POST", apiUrl(`/api/jobs/${id}/details/refresh?force=${force}`)),
  scrape: () => send("POST", apiUrl("/api/scrape")),
  scrapeStatus: () => fetch(apiUrl("/api/scrape/status")).then(j),
  refreshJobDetails: (force = false) => send("POST", apiUrl(`/api/jobs/details/refresh?force=${force}`)),
  jobDetailsStatus: () => fetch(apiUrl("/api/jobs/details/refresh/status")).then(j),
  gmailSync: () => send("POST", apiUrl("/api/gmail/sync")),
  createTracker: (job_id, recipient) => send("POST", apiUrl("/api/track"), { job_id, recipient }),
  trackers: (job_id) => fetch(apiUrl(`/api/track?job_id=${job_id}`)).then(j),
};
