from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def build_pdf_report(session_dir: Path, summary: dict[str, object]) -> Path | None:
    """Write a compact printable report. Returns None only if PDF support is absent."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return None

    pdf_path = session_dir / "report.pdf"
    document = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.leading = 15
    title = styles["Title"]
    story = [
        Paragraph("Machine Vision Inspection Report", title),
        Spacer(1, 4 * mm),
        Paragraph(
            f"Report ID: {html.escape(str(summary['report_id']))}<br/>"
            f"Mode: {html.escape(str(summary['mode']))}<br/>"
            f"Inspected at: {html.escape(str(summary['inspected_at'] or 'No records yet'))}<br/>"
            f"Generated at: {html.escape(str(summary['generated_at']))}",
            body,
        ),
        Spacer(1, 5 * mm),
    ]
    overview = [
        ["Total", "PASS", "FAIL", "Yield"],
        [str(summary["total"]), str(summary["passed"]), str(summary["failed"]), f"{summary['yield_rate']}%"],
    ]
    overview_table = Table(overview, colWidths=[42 * mm] * 4)
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([overview_table, Spacer(1, 5 * mm)])

    breakdown = summary.get("failure_breakdown", {})
    breakdown_text = ", ".join(f"{key}: {value}" for key, value in breakdown.items()) or "None"
    story.extend([Paragraph(f"Failure breakdown: {html.escape(breakdown_text)}", body), Spacer(1, 4 * mm)])

    rows = [["No.", "Time", "Verdict", "Result"]]
    for record in summary.get("records", []):
        rows.append([
            str(record.get("sequence", "")),
            str(record.get("timestamp", "")),
            str(record.get("verdict", "")),
            str(record.get("detection_message", "")),
        ])
    if len(rows) == 1:
        rows.append(["-", "-", "-", "No inspection records yet"])
    records_table = Table(rows, colWidths=[14 * mm, 42 * mm, 24 * mm, 88 * mm], repeatRows=1)
    records_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(records_table)
    document.build(story)
    return pdf_path


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
        "inspected_at": records[-1].get("timestamp", "") if records else "",
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
    build_pdf_report(session_dir, summary)
    sync_mini_program_reports(session_dir.parents[1])
    return json_path, html_path


def sync_mini_program_reports(project_root: Path) -> Path:
    """Aggregate desktop report JSON files into a local mini-program data file.

    This makes report data visible in WeChat Developer Tools without a backend.
    A real phone release will reuse this exact data format through cloud storage.
    """
    summaries: list[dict[str, object]] = []
    for report_path in sorted((project_root / "results").glob("session_*/report.json"), reverse=True):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        breakdown = report.get("failure_breakdown", {})
        summaries.append({
            "id": report.get("report_id", report_path.parent.name),
            "mode": report.get("mode", "Unknown"),
            "time": report.get("inspected_at") or report.get("generated_at", ""),
            "total": report.get("total", 0),
            "passed": report.get("passed", 0),
            "failed": report.get("failed", 0),
            "yieldRate": f"{report.get('yield_rate', 0)}%",
            "verdict": "PASS" if report.get("failed", 0) == 0 else "FAIL",
            "result": "PASS" if report.get("failed", 0) == 0 else "FAIL " + " / ".join(name.removeprefix("FAIL ") for name in breakdown.keys()),
            "defects": [name.removeprefix("FAIL ") for name in breakdown.keys()],
            "note": "Automatically synchronized from the desktop inspection report.",
        })
    runtime_path = project_root / "miniprogram" / "mock" / "runtime_reports.js"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_path.write_text(
        "// Generated by pc_app/report_generator.py. Do not edit manually.\n"
        + "module.exports = "
        + json.dumps(summaries, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return runtime_path
