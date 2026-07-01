# Scale Army — UGC Creative Performance Dashboard

Tracks, per month, how UGC ("user-generated content" style) ad creatives perform
against the rest of the paid ads account: SQL volume, spend allocation, cost per
SQL, and whether UGC is over- or under-indexed relative to the budget it gets.

**Live dashboard:** published via GitHub Pages from this repo (Settings → Pages
→ source: GitHub Actions). URL appears in the `deploy` job summary after the
first successful workflow run.

## ⚠️ Definitions — do not change silently

**SQL definition:** `sql == "Yes"` on the `MB - Since 10/25` or `MH - Since 10/25`
tab, anchored to the **`Date entered "Meeting Scheduled (Placements — MRR Inbound
Sales)"`** column for monthly grouping. This is *not* a lifecycle-stage-entered
timestamp — those were confirmed to overcount SQLs due to stage re-entries and
automations. `MB` is the primary source; the small set of contacts that are SQL
on `MH` but never appear on `MB` are added using MH's own Meeting Scheduled date
so they aren't dropped.

**UGC definition:** the **raw** `utm_content` value (HubSpot side) or the ad's
`ad_name` (Meta side) contains the substring `"ugc"`, case-insensitive. This is
checked on the raw value, not the alias-resolved name — confirmed to produce
identical results here since UGC-tagged ads already use their canonical name as
`utm_content` directly.

If either definition needs to change, update `pipeline/sheets.py` /
`pipeline/meta.py` **and** this section together.

## How it works

```
pipeline/sheets.py    → pulls contacts from Google Sheets (New Leads, MB, MH,
                         No Show/Cancelled tabs) via a service account
pipeline/meta.py      → pulls ad-level spend from the Meta Marketing API
pipeline/analysis.py  → joins the two, computes monthly UGC vs. non-UGC metrics
pipeline/main.py      → CLI entrypoint, writes data/monthly_analysis.json
docs/                 → static dashboard (HTML/CSS/JS + Chart.js) that reads
                         docs/data/monthly_analysis.json
```

The creative join works like this: HubSpot's `utm_content` is often a messy,
historical value (e.g. `[JERRICA] [SOCIAL MEDIA] [08]`). The `ad_aliases` tab in
the source sheet maps these raw values to the canonical Meta ad name (e.g.
`AD02_VID_Jerrica_80k_year_SMM`), which is what the Meta Marketing API returns
as `ad_name`. The pipeline resolves this mapping to join HubSpot SQLs to Meta
spend per creative.

## Running the pipeline locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export SHEET_ID=1szR5aHU5j1FijE4mBVmlx2A0AsA7-lvocgsbO6UFmCw   # optional, this is the default
export META_ACCESS_TOKEN=...
export META_ACCOUNT_IDS=2253775124815235,987253545601759

# Full history (earliest SQL month → current month):
python3 -m pipeline.main --output data/monthly_analysis.json

# A specific range:
python3 -m pipeline.main --start 2026-04 --end 2026-06 --output data/monthly_analysis.json

# Preview the dashboard against your local output:
cp data/monthly_analysis.json docs/data/monthly_analysis.json
python3 -m http.server 8000 --directory docs
# open http://localhost:8000
```

The Google service account needs **read access** to the source spreadsheet
(share it with the service account's email) and the Meta token needs
`ads_read` on both ad accounts.

## GitHub Actions deploy workflow

`.github/workflows/deploy.yml`:

- **Triggers:** daily at 09:00 UTC, on manual dispatch (Actions tab → "Run
  workflow"), and on push to `main` that touches `docs/`, `pipeline/`, or the
  workflow file itself.
- **What it does:** installs Python deps, runs the pipeline for the full
  available history, copies the resulting JSON into `docs/data/`, and deploys
  `docs/` to GitHub Pages via `actions/upload-pages-artifact` +
  `actions/deploy-pages` (no committed data files, no `gh-pages` branch).
- Daily was chosen over weekly because spend and SQL counts change often enough
  during active testing periods that stakeholders checking mid-week would
  otherwise see stale numbers; change the cron in the workflow if you'd rather
  run weekly.

### One-time repo setup

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions**, add:
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — the full contents of the service account's
     JSON key file (not a path).
   - `SHEET_ID` — the source spreadsheet ID (optional; defaults to the ID
     hardcoded in `pipeline/sheets.py` if omitted).
   - `META_ACCESS_TOKEN` — Meta Marketing API access token with `ads_read`.
   - `META_ACCOUNT_IDS` — comma-separated ad account IDs, with or without the
     `act_` prefix.
3. Push to `main` or trigger the workflow manually to run the first deploy.

### Updating credentials

Rotate a secret with:

```bash
gh secret set META_ACCESS_TOKEN --repo <owner>/<repo>
gh secret set GOOGLE_SERVICE_ACCOUNT_JSON --repo <owner>/<repo> < service-account.json
```

Never commit `gcp_credentials.json`, `.env`, or any token to the repo — both
are already in `.gitignore`.
