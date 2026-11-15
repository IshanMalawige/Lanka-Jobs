# LankaJobs: IT Job Aggregator and Application Tracker

Collects IT roles in Sri Lanka (TopJobs, ITPro, Xpress Jobs, and LinkedIn), tracks postings from the
configured bank career pages under Banking, and tracks each application on a Kanban board.

```
backend/    FastAPI + SQLAlchemy (scrapers, filter, Gmail parser, tracking pixel, skill gap)
frontend/   React + Tailwind (Dashboard job feed, Applications board)
extension/  Manifest V3 Chrome/Brave extension (one-click save)
```

## 1. Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # edit MY_SKILLS etc.
uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs. The first search runs when the backend starts; scrapers then run every `SCRAPE_INTERVAL_MINUTES`.
Newly collected jobs also save their description, requirements, application instructions, and available job-ad image when the source page provides them. Some listings may no longer expose their full details. Bank career pages are checked on the existing scraper schedule; the dashboard includes direct links for all configured banks and the Central Bank recruitment portal.

## 2. Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```
Upload or replace your PDF CV from the dashboard to personalize the automatic job matches. Only detected skill names are saved locally; the PDF itself is discarded.

## 3. Deploy (Vercel + Render)
The frontend is deployed to Vercel and the FastAPI backend plus PostgreSQL database to Render. The root `vercel.json` and `render.yaml` contain the deployment settings.

1. Push this project to a GitHub repository.
2. In Render, create a Blueprint from the repository and accept the web service and PostgreSQL database. Set `CORS_ORIGINS` to the Vercel site URL and `PUBLIC_BASE_URL` to the Render API URL.
3. In Vercel, import the same repository and set `VITE_API_URL` to the Render API URL (for example, `https://lankajobs-api.onrender.com`).
4. After Vercel assigns the site URL, ensure that exact URL is included in Render's `CORS_ORIGINS`, then redeploy the backend.

The included Render services use free plans for testing. Free Render web services can sleep when idle, and free PostgreSQL databases expire after 30 days; the scheduler is not suitable for continuous operation on a sleeping service. The deployed app has no login, so anyone with its public URL can view and change its data or trigger scraping.

## 4. Browser extension
Chrome/Brave -> `chrome://extensions` -> Developer mode -> Load unpacked -> select `extension/`.
Open any job page, click the extension, edit title/company if needed, Save.

## 5. Gmail status updates (optional)
1. Google Cloud Console: create a project and enable the **Gmail API**.
2. OAuth consent screen (External; add yourself as test user), then create an **OAuth client ID (Desktop)**.
3. Save the JSON as `backend/credentials.json`.
4. `cd backend && python -m app.services.gmail_parser` (browser login once; read-only scope).
5. The scheduler then checks mail every `GMAIL_SYNC_INTERVAL_MINUTES`. "Thank you for applying" -> Applied,
   "interview/assessment" -> Interview, "pleased to offer" -> Offer, "regret/unfortunately" -> Rejected.
   Matching is by company name, so keep company names accurate. Statuses never move backwards (except to Rejected).

## 6. Tracking pixel
Card -> Details -> **Tracked email snippet**, then paste the `<img>` into the HTML body of your email.
Opens are recorded at `/api/track/<token>.gif`. Important limits:
- The backend must be reachable from the internet (set `PUBLIC_BASE_URL`, e.g. via a Cloudflare Tunnel or a small VPS), otherwise recipients' mail clients cannot load it.
- Apple Mail and Gmail pre-load images, so counts can be false positives; blocked images give false negatives.
- It's good practice to say in your email that you use read receipts.

## 7. Customising
- **Target roles:** `backend/app/filters.py` (regex per category).
- **Scrapers:** `backend/app/scrapers/` - TopJobs URLs, ITPro/Xpress Jobs categories, and `BANKING_SOURCES` in `careers.py` configure monitored official job pages. Public openings are collected automatically; sites that require sign-in or client-side interaction remain available through their dashboard links.
- **Skills:** `MY_SKILLS` in `.env`; the known-skills vocabulary is in `services/skill_gap.py`.

## 8. Notes
- LinkedIn's terms restrict automated scraping. The included guest-search scraper is slow, small and for personal use; the extension is the safer route for LinkedIn jobs. Respect each site's robots.txt/terms.
- Auto-apply is intentionally not included: this tool tracks and organises applications rather than submitting them for you.
- Next ideas: PostgreSQL + Alembic migrations, auth if you deploy publicly, Docker Compose, Telegram/email alerts for new jobs.
