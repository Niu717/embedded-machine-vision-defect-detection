from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def build_session_report(session_dir: Path, mode: str) -> tuple[Path, Path]:
    """Create portable JSON and HTML reports from one inspection session."""
    csv_path = session_dir / "detections.csv"
    records: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
            records = list(csv.DictReader(file))

    total = len(records)
    passed = sum(record.get("verdict") == "PASS" for record in records)
    failures = Counter(
        record.get("detection_message", "FAIL") for record in records
        if record.get("verdict") == "FAIL"
    )
    summary = {
        "report_id": session_dir.name,
        "mode": mode,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "yield_rate": round(passed * 100 / total, 1) if total else 0.0,
        "failure_breakdown": dict(failures),
        "records": records,
    }
    json_path = session_dir / "report.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(record.get('sequence', ''))}</td>"
        f"<td>{html.escape(record.get('timestamp', ''))}</td>"
        f"<td class=\"{record.get('verdict', '').lower()}\">{html.escape(record.get('verdict', ''))}</td>"
        f"<td>{html.escape(record.get('detection_message', ''))}</td>"
        f"<td>{html.escape(record.get('annotated_image', ''))}</td>"
        "</tr>"
        for record in records
    ) or "<tr><td colspan=\"5\">No inspection records yet.</td></tr>"
    failures_text = ", ".join(f"{name}: {count}" for name, count in failures.items()) or "None"
    html_path = session_dir / "report.html"
    html_path.write_text(
        f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>Inspection Report</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;background:#f4f7fb;color:#172033;margin:36px}}h1{{margin-bottom:4px}}.subtitle{{color:#64748b}}.cards{{display:flex;gap:12px;margin:24px 0}}.card{{background:#fff;border-radius:12px;padding:16px 20px;min-width:130px;box-shadow:0 2px 10px #dbe4f055}}.value{{font-size:26px;font-weight:700;color:#0f766e}}table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}}th,td{{padding:11px;border-bottom:1px solid #e6edf5;text-align:left}}th{{background:#102a43;color:#fff}}.pass{{color:#15803d;font-weight:700}}.fail{{color:#dc2626;font-weight:700}}</style></head>
<body><h1>Machine Vision Inspection Report</h1><p class=\"subtitle\">Report ID: {html.escape(session_dir.name)} &nbsp; Mode: {html.escape(mode)} &nbsp; Generated: {summary['generated_at']}</p>
<div class=\"cards\"><div class=\"card\">Total<div class=\"value\">{total}</div></div><div class=\"card\">PASS<div class=\"value\">{passed}</div></div><div class=\"card\">FAIL<div class=\"value\">{total-passed}</div></div><div class=\"card\">Yield<div class=\"value\">{summary['yield_rate']}%</div></div></div>
<p><b>Failure breakdown:</b> {html.escape(failures_text)}</p><table><thead><tr><th>No.</th><th>Time</th><th>Verdict</th><th>Result</th><th>Annotated image</th></tr></thead><tbody>{rows}</tbody></table></body></html>""",
        encoding="utf-8",
    )
    return json_path, html_path
