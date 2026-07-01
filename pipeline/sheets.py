"""Pull contact/SQL data from the Scale Army source-of-truth Google Sheet.

SQL definition (do not change without updating README.md):
    sql == "Yes" on the MB or MH tab, anchored to the
    'Date entered "Meeting Scheduled (Placements — MRR Inbound Sales)"' column.
    This was validated against known-correct monthly SQL counts.

UGC definition:
    utm_content contains the substring "ugc" (case-insensitive), checked on the
    RAW utm_content value as stored in the sheet (not the alias-resolved name).
"""
import os
import re
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("SHEET_ID", "1szR5aHU5j1FijE4mBVmlx2A0AsA7-lvocgsbO6UFmCw")

TAB_NEW_LEADS = "New Leads - Since 10/25"
TAB_MB = "MB - Since 10/25"
TAB_MH = "MH - Since 10/25"
TAB_NO_SHOW = "No Show/Cancelled - Since 10/25"
TAB_AD_ALIASES = "ad_aliases"

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _client() -> gspread.Client:
    """Build an authorized gspread client from a service account.

    Accepts credentials either as a path (GOOGLE_APPLICATION_CREDENTIALS) or as
    raw JSON in the GOOGLE_SERVICE_ACCOUNT_JSON env var (used in CI).
    """
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        import json
        info = json.loads(raw_json)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "gcp_credentials.json")
        creds = Credentials.from_service_account_file(path, scopes=_SCOPES)
    return gspread.authorize(creds)


def _month_of(date_str: str):
    date_str = (date_str or "").strip()
    if not date_str or date_str == "(No value)":
        return None
    return date_str[:7]  # "YYYY-MM"


def load_ad_aliases(sh) -> dict:
    """Return {utm_content.lower(): canonical_ad_name} for spend-matching."""
    rows = sh.worksheet(TAB_AD_ALIASES).get_all_values()[1:]
    aliases = {}
    for r in rows:
        if len(r) >= 2 and r[0] and r[1]:
            aliases[r[0].strip().lower()] = r[1].strip()
    return aliases


def resolve_ad_name(utm_content: str, aliases: dict) -> str:
    """Map a raw utm_content value to the canonical Meta ad_name, if known."""
    return aliases.get((utm_content or "").strip().lower(), (utm_content or "").strip())


def is_ugc(raw_utm_content: str) -> bool:
    return bool(re.search(r"ugc", raw_utm_content or "", re.IGNORECASE))


def _contact_from_row(row, date_idx, email_idx, attr_idx, utm_content_idx, sql_idx):
    if len(row) <= max(date_idx, email_idx, attr_idx, utm_content_idx, sql_idx):
        return None
    month = _month_of(row[date_idx])
    if not month:
        return None
    email = (row[email_idx] or "").strip().lower()
    if not email:
        return None
    return {
        "email": email,
        "month": month,
        "attribution": (row[attr_idx] or "").strip(),
        "utm_content_raw": (row[utm_content_idx] or "").strip(),
        "sql": (row[sql_idx] or "").strip() == "Yes",
    }


def load_sql_contacts(sh) -> list:
    """Return the deduplicated list of SQL-eligible contacts (MB ∪ MH by email).

    MB is the primary source (has the validated date-anchor column). A small
    set of contacts are SQL on the MH tab but never appear on MB — those are
    added using MH's own "Meeting Scheduled" date so they aren't undercounted.
    """
    mb_rows = sh.worksheet(TAB_MB).get_all_values()[1:]
    mh_rows = sh.worksheet(TAB_MH).get_all_values()[1:]

    # MB columns: 0=Meeting Scheduled date, 2=Email, 3=Attribution, 7=utm_content, 10=SQL
    contacts = {}
    for row in mb_rows:
        c = _contact_from_row(row, date_idx=0, email_idx=2, attr_idx=3, utm_content_idx=7, sql_idx=10)
        if c:
            contacts[c["email"]] = c

    # MH columns: 1=Meeting Scheduled date, 3=Email, 4=Attribution, 8=utm_content, 11=SQL
    for row in mh_rows:
        c = _contact_from_row(row, date_idx=1, email_idx=3, attr_idx=4, utm_content_idx=8, sql_idx=11)
        if c and c["email"] not in contacts:
            contacts[c["email"]] = c

    return list(contacts.values())


def fetch_all():
    """Fetch everything the pipeline needs from the sheet in one pass."""
    gc = _client()
    sh = gc.open_by_key(SHEET_ID)
    aliases = load_ad_aliases(sh)
    contacts = load_sql_contacts(sh)
    for c in contacts:
        c["ad_name"] = resolve_ad_name(c["utm_content_raw"], aliases)
        c["is_ugc"] = is_ugc(c["utm_content_raw"])
    return contacts
