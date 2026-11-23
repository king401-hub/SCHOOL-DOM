"""HTML builders for Attendance Analytics PDF reports - handed to
finance.pdf.render_html_to_pdf (the same headless-Chromium pipeline already
used in production for receipts, bills and report cards), never a new PDF
library. Every number here comes straight from services.py's own screen
functions - a report can never show a figure the dashboard itself wouldn't,
per the brief's own acceptance criterion that "PDF and Excel reports
reconcile with dashboard figures."

CSV export (the brief's "Excel" deliverable) lives in views.py directly -
plain csv module, matching the existing "Export to Excel" convention
elsewhere in this codebase (which is itself CSV, not real .xlsx)."""
from django.utils import timezone
from django.utils.html import escape

from users.app_views import _school_identity_payload

from . import services

REPORT_CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; color: #0f172a; margin: 0; padding: 24px; }
.report-header { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 18px; }
.report-header img { width: 56px; height: 56px; object-fit: contain; border-radius: 8px; }
.report-header h1 { font-size: 1.3rem; margin: 0; }
.report-header p { margin: 2px 0 0; color: #64748b; font-size: 0.85rem; }
.report-meta { color: #64748b; font-size: 0.8rem; margin-bottom: 16px; }
.report-stats { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }
.report-stat { border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; min-width: 120px; }
.report-stat .label { font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.03em; }
.report-stat .value { font-size: 1.2rem; font-weight: 700; }
table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.82rem; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }
th { background: #f8fafc; color: #334155; }
h2 { font-size: 1rem; margin: 24px 0 8px; }
"""


def _shell(title, school, period_label, body_html):
    logo_html = f'<img src="{escape(school["logo"])}" alt="">' if school.get("logo") else ""
    generated_at = timezone.localtime().strftime("%d %b %Y, %I:%M %p").lstrip("0")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{REPORT_CSS}</style></head>
<body>
  <div class="report-header">
    {logo_html}
    <div>
      <h1>{escape(school["name"])}</h1>
      <p>{escape(title)} - {escape(period_label)}</p>
    </div>
  </div>
  <div class="report-meta">Generated {escape(generated_at)}</div>
  {body_html}
</body></html>"""


def _stat(label, value):
    return f'<div class="report-stat"><div class="label">{escape(str(label))}</div><div class="value">{escape(str(value))}</div></div>'


def _register_table(rows):
    body_rows = "".join(
        f"<tr><td>{escape(r['name'])}</td><td>{escape(r['identifier'] or '')}</td>"
        f"<td>{escape(r['group_label'] or '')}</td><td>{escape(r['first_arrival'] or '-')}</td>"
        f"<td>{escape(r['last_departure'] or '-')}</td><td>{escape(str(r['total_hours']) if r['total_hours'] is not None else '-')}</td>"
        f"<td>{escape(r['status'])}</td></tr>"
        for r in rows
    )
    return f"""<table>
<thead><tr><th>Name</th><th>ID</th><th>Class/Dept</th><th>First arrival</th><th>Last departure</th><th>Hours</th><th>Status</th></tr></thead>
<tbody>{body_rows}</tbody></table>"""


def daily_report_html(tenant, request, population, target_date):
    school = _school_identity_payload(tenant, request)
    summary = services.daily_summary(tenant, population, target_date)
    register = services.daily_register(tenant, population, target_date, page=1, page_size=10000)
    stats = summary["summary"]
    body = (
        '<div class="report-stats">'
        + _stat("Registered", stats["total_registered"])
        + _stat("Present", stats["total_present"])
        + _stat("Absent", stats["total_absent"])
        + _stat("Attendance %", f"{stats['attendance_percent']}%")
        + "</div>"
        + _register_table(register["results"])
    )
    return _shell(f"Daily Attendance Report ({population.title()})", school, target_date.isoformat(), body)


def staff_report_html(tenant, request, person_id, period, period_start, period_end):
    school = _school_identity_payload(tenant, request)
    data = services.staff_profile_summary(tenant, person_id, period_start, period_end)
    history = services.staff_history(tenant, person_id, period_start, period_end, page=1, page_size=10000)
    stats = data["stats"]
    body = (
        f'<h2>{escape(data["person"]["name"])} - {escape(data["person"].get("department") or "")}</h2>'
        + '<div class="report-stats">'
        + _stat("Days present", stats["days_present"])
        + _stat("Days absent", stats["days_absent"])
        + _stat("Expected days", stats["expected_working_days"])
        + _stat("Attendance %", f"{stats['attendance_percent']}%")
        + (_stat("Total hours", stats["total_hours"]) if stats["total_hours"] is not None else "")
        + (_stat("Late arrivals", stats["late_arrivals"]) if stats["late_arrivals"] is not None else "")
        + "</div>"
        + _register_table([{**r, "name": r["date"], "identifier": "", "group_label": ""} for r in history["results"]])
    )
    return _shell("Individual Staff Attendance Report", school, f"{period_start} to {period_end} ({period})", body)


def student_report_html(tenant, request, student_id, period, period_start, period_end):
    school = _school_identity_payload(tenant, request)
    data = services.student_profile_summary(tenant, student_id, period_start, period_end)
    history = services.student_history(tenant, student_id, period_start, period_end, page=1, page_size=10000)
    stats = data["stats"]
    body = (
        f'<h2>{escape(data["person"]["name"])} - {escape(data["person"].get("class_name") or "")} {escape(data["person"].get("arm") or "")}</h2>'
        + '<div class="report-stats">'
        + _stat("Days present", stats["days_present"])
        + _stat("Days absent", stats["days_absent"])
        + _stat("Expected days", stats["expected_working_days"])
        + _stat("Attendance %", f"{stats['attendance_percent']}%")
        + "</div>"
        + _register_table([{**r, "name": r["date"], "identifier": "", "group_label": ""} for r in history["results"]])
    )
    return _shell("Individual Student Attendance Report", school, f"{period_start} to {period_end} ({period})", body)


def class_department_report_html(tenant, request, population, period, period_start, period_end):
    school = _school_identity_payload(tenant, request)
    groups = services.class_department_comparison(tenant, population, period_start, period_end)
    label = "Class" if population == "student" else "Department"
    rows = "".join(
        f"<tr><td>{escape(g['group_label'])}</td><td>{g['total_people']}</td><td>{g['total_present']}</td><td>{g['attendance_percent']}%</td></tr>"
        for g in groups
    )
    body = f"""<table>
<thead><tr><th>{escape(label)}</th><th>Total</th><th>Present</th><th>Attendance %</th></tr></thead>
<tbody>{rows}</tbody></table>"""
    title = f"{label} Attendance Comparison ({population.title()})"
    return _shell(title, school, f"{period_start} to {period_end} ({period})", body)


def termly_report_html(tenant, request):
    school = _school_identity_payload(tenant, request)
    overview = services.term_overview(tenant)
    start, end = services.term_date_range(tenant)

    sections = [f'<h2>Term: {escape(overview["term"]["name"] or "Current term")}</h2>']
    for population_key, label in (("staff", "Staff"), ("students", "Students")):
        pop_data = overview.get(population_key)
        if not pop_data:
            continue
        sections.append(f"<h2>{label}</h2>")
        sections.append(
            '<div class="report-stats">'
            + _stat("Total people", pop_data["total_people"])
            + _stat("Days present", pop_data["total_days_present"])
            + _stat("Absences", pop_data["total_absences"])
            + _stat("Attendance %", f"{pop_data['average_attendance_percent']}%")
            + (_stat("Total hours", pop_data["total_hours"]) if pop_data.get("total_hours") is not None else "")
            + "</div>"
        )
        population_arg = "student" if population_key == "students" else "staff"
        groups = services.class_department_comparison(tenant, population_arg, start, end)
        group_label = "Class" if population_arg == "student" else "Department"
        rows = "".join(
            f"<tr><td>{escape(g['group_label'])}</td><td>{g['total_people']}</td><td>{g['total_present']}</td><td>{g['attendance_percent']}%</td></tr>"
            for g in groups
        )
        sections.append(f"""<table>
<thead><tr><th>{escape(group_label)}</th><th>Total</th><th>Present</th><th>Attendance %</th></tr></thead>
<tbody>{rows}</tbody></table>""")

        rankings = services.rankings(tenant, population_arg, start, end)
        for key, items in rankings.items():
            if not items:
                continue
            label_text = key.replace("_", " ").title()
            list_items = "".join(f"<li>{escape(p['name'])} - {p.get('attendance_percent', p.get('late_arrivals', p.get('total_hours', '')))}</li>" for p in items)
            sections.append(f"<h2>{escape(label_text)}</h2><ol>{list_items}</ol>")

    return _shell("Comprehensive Termly Attendance Report", school, f"{overview['term']['start_date']} to {overview['term']['end_date']}", "".join(sections))
