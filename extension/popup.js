const $ = (id) => document.getElementById(id);
let page = { url: "", description: "" };

// Runs inside the page: reads structured data (JSON-LD JobPosting) first, then falls back to meta tags / headings.
function extractJob() {
  const out = { title: "", company: "", description: "", url: location.href, posted: null };
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const data = JSON.parse(s.textContent);
      const items = Array.isArray(data) ? data : data["@graph"] || [data];
      const jp = items.find((i) => i["@type"] === "JobPosting");
      if (jp) {
        out.title = jp.title || "";
        out.company = (jp.hiringOrganization && jp.hiringOrganization.name) || "";
        out.description = (jp.description || "").replace(/<[^>]+>/g, " ").slice(0, 4000);
        out.posted = jp.datePosted || null;
        break;
      }
    } catch (e) { /* ignore bad JSON-LD */ }
  }
  if (!out.title) {
    const h1 = document.querySelector("h1");
    out.title = (h1 && h1.innerText.trim()) || document.title;
  }
  if (!out.company) {
    const og = document.querySelector('meta[property="og:site_name"]');
    out.company = (og && og.content) || location.hostname.replace(/^www\./, "");
  }
  if (!out.description) {
    const meta = document.querySelector('meta[name="description"]');
    out.description = ((meta && meta.content) || document.body.innerText).slice(0, 4000);
  }
  out.url = out.url.split("#")[0];
  return out;
}

(async () => {
  const saved = await chrome.storage.local.get("api");
  if (saved.api) $("api").value = saved.api;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  try {
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractJob });
    page = result;
    $("title").value = result.title;
    $("company").value = result.company;
  } catch (e) {
    $("title").value = tab.title || "";
    page = { url: tab.url, description: "" };
  }
})();

$("save").onclick = async () => {
  const api = $("api").value.replace(/\/$/, "");
  await chrome.storage.local.set({ api });
  $("status").textContent = "Saving…";
  try {
    const res = await fetch(`${api}/api/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: $("title").value, company: $("company").value, url: page.url,
        description: page.description, notes: $("notes").value, source: "extension",
        posted_date: page.posted || null,
      }),
    });
    if (!res.ok) throw new Error(res.status);
    $("status").textContent = "Saved. Open the dashboard to see it.";
  } catch (e) {
    $("status").textContent = "Could not reach the API. Is the backend running at " + api + "?";
  }
};
