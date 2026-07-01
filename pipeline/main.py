"""CLI entrypoint for the UGC creative performance pipeline.

Usage:
    python -m pipeline.main --start 2026-04 --end 2026-06 --output data/monthly_analysis.json

If --start/--end are omitted, the pipeline covers every month present in the
source sheet, from the earliest SQL record through the current month.
"""
import argparse
import json
import sys
from datetime import date, datetime

from . import sheets, analysis


def _month_range(start: str, end: str) -> list:
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Build the UGC creative performance JSON.")
    p.add_argument("--start", help="First month, format YYYY-MM")
    p.add_argument("--end", help="Last month, format YYYY-MM")
    p.add_argument("--output", default="data/monthly_analysis.json", help="Output JSON path")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    print("[pipeline] fetching contacts from Google Sheet...", file=sys.stderr)
    contacts = sheets.fetch_all()
    if not contacts:
        print("[pipeline] ERROR: no contacts loaded — check credentials/sheet ID", file=sys.stderr)
        return 1

    start = args.start or min(c["month"] for c in contacts)
    end = args.end or date.today().strftime("%Y-%m")
    months = _month_range(start, end)
    print(f"[pipeline] building report for {start}..{end} ({len(months)} months)", file=sys.stderr)

    report = analysis.build_report(months, contacts)
    report["generated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    report["range"] = {"start": start, "end": end}

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[pipeline] wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
