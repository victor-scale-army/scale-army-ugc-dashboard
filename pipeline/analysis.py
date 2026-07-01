"""Join HubSpot SQL data with Meta spend data and compute monthly UGC metrics."""
from collections import defaultdict

from . import meta


def _safe_div(num, den):
    return round(num / den, 2) if den else None


def compute_month(month: str, contacts: list, spend_by_ad: dict) -> dict:
    month_contacts = [c for c in contacts if c["month"] == month]

    total_sql = sum(1 for c in month_contacts if c["sql"])
    ugc_sql = sum(1 for c in month_contacts if c["sql"] and c["is_ugc"])
    non_ugc_sql = total_sql - ugc_sql

    creative_sql = defaultdict(int)
    for c in month_contacts:
        if c["sql"] and c["is_ugc"]:
            creative_sql[c["ad_name"] or c["utm_content_raw"] or "(unknown)"] += 1
    creatives = [
        {"ad_name": name, "sql": n}
        for name, n in sorted(creative_sql.items(), key=lambda kv: -kv[1])
    ]

    total_spend = round(sum(spend_by_ad.values()), 2)
    ugc_spend = round(sum(v for k, v in spend_by_ad.items() if meta.is_ugc_ad_name(k)), 2)
    non_ugc_spend = round(total_spend - ugc_spend, 2)

    pct_sql_from_ugc = round(ugc_sql / total_sql * 100, 1) if total_sql else None
    pct_spend_ugc = round(ugc_spend / total_spend * 100, 1) if total_spend else None

    cost_per_sql_ugc = _safe_div(ugc_spend, ugc_sql)
    cost_per_sql_non_ugc = _safe_div(non_ugc_spend, non_ugc_sql)
    cost_per_sql_blended = _safe_div(total_spend, total_sql)

    gap_pct = (
        round(pct_sql_from_ugc - pct_spend_ugc, 1)
        if pct_sql_from_ugc is not None and pct_spend_ugc is not None
        else None
    )

    return {
        "month": month,
        "total_sql": total_sql,
        "ugc_sql": ugc_sql,
        "non_ugc_sql": non_ugc_sql,
        "pct_sql_from_ugc": pct_sql_from_ugc,
        "creatives": creatives,
        "total_spend": total_spend,
        "ugc_spend": ugc_spend,
        "non_ugc_spend": non_ugc_spend,
        "pct_spend_ugc": pct_spend_ugc,
        "cost_per_sql_ugc": cost_per_sql_ugc,
        "cost_per_sql_non_ugc": cost_per_sql_non_ugc,
        "cost_per_sql_blended": cost_per_sql_blended,
        # positive => UGC produces more SQL-share than its spend-share (efficient / under-funded)
        # negative => UGC consumes more spend-share than its SQL-share (inefficient / over-funded)
        "spend_sql_gap_pct": gap_pct,
    }


def build_report(months: list, contacts: list) -> dict:
    results = []
    for month in months:
        spend_by_ad = meta.fetch_ad_spend_for_month(month)
        results.append(compute_month(month, contacts, spend_by_ad))
    return {
        "sql_definition": (
            "sql == 'Yes' on the MB/MH tabs, anchored to the "
            "'Date entered \"Meeting Scheduled (Placements — MRR Inbound Sales)\"' date."
        ),
        "ugc_definition": (
            "utm_content (HubSpot) or ad_name (Meta) contains the substring 'ugc', "
            "case-insensitive."
        ),
        "months": results,
    }
