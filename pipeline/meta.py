"""Pull Meta Ads spend by ad name, by month.

UGC classification on the spend side is done the same way as on the HubSpot
side: the ad's own `ad_name` (as returned by Meta) contains the substring
"ugc" (case-insensitive). This is consistent because canonical ad names
(e.g. AD174_VID_UGC_SMM_...) are what utm_content resolves to via ad_aliases.
"""
import os
import re
import calendar
import httpx

META_GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _accounts():
    raw = os.environ.get("META_ACCOUNT_IDS", "")
    ids = [a.strip() for a in raw.split(",") if a.strip()]
    return [a if a.startswith("act_") else f"act_{a}" for a in ids]


def _token():
    return os.environ.get("META_ACCESS_TOKEN", "")


def is_ugc_ad_name(ad_name: str) -> bool:
    return bool(re.search(r"ugc", ad_name or "", re.IGNORECASE))


def month_bounds(month: str):
    """'2026-04' -> ('2026-04-01', '2026-04-30')."""
    year, mon = (int(x) for x in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last_day:02d}"


def fetch_ad_spend_for_month(month: str) -> dict:
    """Return {ad_name: spend_float} aggregated across all configured accounts."""
    since, until = month_bounds(month)
    token = _token()
    spend_by_ad: dict = {}
    if not token or not _accounts():
        return spend_by_ad
    for acc in _accounts():
        url = f"{META_GRAPH_BASE}/{acc}/insights"
        params = {
            "access_token": token,
            "level": "ad",
            "fields": "ad_name,spend",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "limit": 500,
        }
        while url:
            r = httpx.get(url, params=params, timeout=60)
            r.raise_for_status()
            payload = r.json()
            for row in payload.get("data", []):
                name = (row.get("ad_name") or "").strip()
                if not name:
                    continue
                spend_by_ad[name] = spend_by_ad.get(name, 0.0) + float(row.get("spend", 0) or 0)
            paging = payload.get("paging", {})
            url = paging.get("next")
            params = None  # `next` already includes all query params
    return spend_by_ad
