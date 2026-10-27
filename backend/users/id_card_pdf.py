"""Renders a person's ID card (front + back) to a real, text-based PDF via a
headless Chromium (Playwright), for AdminIdCardsScreen's bulk ZIP export -
see app_views.id_card_bulk_export_pdf.

Two earlier approaches were tried and reverted for this feature: a
client-side html2canvas screenshot (pixel-perfect but the "text" is just
picture pixels - nothing selectable, searchable, or editable in any PDF
tool) and a hand-drawn jsPDF recreation (real/editable text, but only an
approximation of the actual CSS design - 3 built-in fonts, no gradients).
This module instead reuses the exact same HTML/CSS the live card preview is
built from (ported from frontend/src/styles.css's .id-card-* rules) and
hands it to a real browser engine to print - the same mechanism behind a
person manually choosing "Save as PDF" from their own browser's print
dialog for a single card, just automated server-side so it can run for many
people in one request. The output is both visually faithful to the on-screen
design AND made of real PDF text, because it's not an approximation of the
browser's rendering - it IS the browser's rendering.
"""
import io
import re
import zipfile

from django.utils.html import escape

CARD_WIDTH_IN = 3.375
CARD_HEIGHT_IN = 2.125

# Keeps a single request from tying up the (Celery-less - see
# finance/services.py's own notes on background work here) web worker for
# too long. Each card is a handful of small images plus simple text, so
# this is a generous ceiling, not a tuned one - revisit against real timing
# once this has run against production traffic.
BULK_EXPORT_LIMIT = 100

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3}([0-9a-fA-F]{3}([0-9a-fA-F]{2})?)?$")


def _safe_css_color(value, fallback):
    """Document theme colors come from the school's own color-picker
    settings, not arbitrary third-party input, but they still get
    interpolated directly into a CSS block below - only ever pass through a
    plain hex color, never anything that could break out of the
    declaration."""
    value = str(value or "").strip()
    return value if _HEX_COLOR_RE.match(value) else fallback


def _safe_font_family(value, fallback="Segoe UI"):
    value = str(value or "").strip().replace('"', "").replace("\\", "")
    return value or fallback


def sanitize_filename(value):
    return re.sub(r'[\\/:*?"<>|]+', "_", str(value or "")).strip()


def _initials(name):
    parts = [part for part in str(name or "").split() if part]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return (name or "SD")[:2].upper()


def _format_date(value):
    if not value:
        return "-"
    try:
        return f"{value:%b} {value.day}, {value:%Y}"
    except (ValueError, TypeError):
        return str(value)


def _gender_display(value):
    normalized = str(value or "").upper()
    return {"M": "Male", "F": "Female", "O": "Other", "N": "Prefer not to say"}.get(normalized, value or "-")


def _detail_rows(person):
    is_student = person.get("person_type") == "student"
    if is_student:
        return [
            ("Admission", _format_date(person.get("admission_or_employment_date"))),
            ("Date of Birth", _format_date(person.get("date_of_birth"))),
            ("Gender", _gender_display(person.get("gender"))),
            ("Blood Group", person.get("blood_group") or "-"),
            ("Guardian", person.get("guardian_name") or "-"),
            ("Phone", person.get("phone") or person.get("guardian_phone") or "-"),
        ]
    return [
        ("Employment", _format_date(person.get("admission_or_employment_date"))),
        ("Date of Birth", _format_date(person.get("date_of_birth"))),
        ("Gender", _gender_display(person.get("gender"))),
        ("Role", person.get("primary_label") or "-"),
        ("Department", person.get("department") or person.get("secondary_label") or "-"),
        ("Phone", person.get("phone") or "-"),
    ]


# Ported from frontend/src/styles.css's .id-card-preview-card through
# .id-card-powered-by rules - the card's own visual design, not the admin
# dashboard chrome around it (.id-card-workspace/-hero/-tools/etc., which
# never appears in an export). Flattened out of the interactive 3D-flip
# layout (.id-card-face position:absolute + rotateY) since each face here
# is printed as its own PDF page, not a stacked, flippable pair.
# --id-card-ink/-muted/-line are fixed (never theme-driven, see
# .id-card-print-area in styles.css); --id-card-teal/-green/--doc-secondary
# are set per school in _document_html below, mirroring themeToCssVars().
_CARD_CSS = """
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body { font-family: var(--doc-font-family, "Segoe UI"), Arial, sans-serif; }
  .id-card-page {
    width: 3.375in; height: 2.125in; overflow: hidden; position: relative;
    background: #ffffff; color: var(--id-card-ink);
    page-break-after: always;
  }
  .id-card-page:last-child { page-break-after: avoid; }
  .id-card-front { display: grid; grid-template-rows: auto auto minmax(0, 1fr) auto; }
  .id-card-back { display: grid; grid-template-rows: 38px minmax(0, 1fr) auto; }

  .id-card-ribbon {
    background: var(--id-card-teal); color: #ffffff; text-align: center; text-transform: uppercase;
    letter-spacing: 0.14em; font-size: 0.6rem; font-weight: 900; padding: 0.22rem 0.55rem;
  }

  .id-card-top, .id-card-back-head { display: flex; gap: 0.55rem; align-items: center; padding: 0.4rem 0.62rem; position: relative; overflow: hidden; }
  .id-card-top { background: linear-gradient(120deg, var(--id-card-teal), var(--doc-secondary, #0f172a) 150%); }
  .id-card-back-head { padding: 0.34rem 0.62rem; background: #102033; }
  .id-card-top::after {
    content: ""; position: absolute; inset: 0; z-index: 0;
    background: linear-gradient(115deg, rgba(255, 255, 255, 0.16) 0%, rgba(255, 255, 255, 0) 38%);
  }
  .id-card-school-logo {
    width: 30px; height: 30px; border-radius: 8px; background: #ffffff; flex: 0 0 auto;
    box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.55); position: relative; z-index: 1;
    display: grid; place-items: center; font-weight: 900; color: var(--id-card-teal); font-size: 0.5rem; overflow: hidden;
  }
  .id-card-school-logo img { width: 100%; height: 100%; object-fit: contain; }
  .id-card-top strong, .id-card-top span, .id-card-back-head strong, .id-card-back-head span { display: block; position: relative; z-index: 1; }
  .id-card-top strong, .id-card-back-head strong { font-size: 0.72rem; line-height: 1.05; color: #ffffff; }
  .id-card-top span { color: rgba(255, 255, 255, 0.78); font-size: 0.52rem; margin-top: 0.08rem; }
  .id-card-back-head span { margin-top: 0.08rem; color: #cbd5e1; font-size: 0.52rem; }
  .id-card-motto { display: block; color: #d7ecff; font-size: 0.5rem; font-style: italic; font-weight: 800; margin-top: 0.06rem; }
  .id-card-back-head .id-card-motto { color: #a7f3d0; }

  .id-card-front-body {
    display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 0.45rem;
    padding: 0.42rem 0.62rem 0.35rem;
    background-image: repeating-linear-gradient(
      -35deg,
      color-mix(in srgb, var(--id-card-teal) 5%, transparent) 0px,
      color-mix(in srgb, var(--id-card-teal) 5%, transparent) 1px,
      transparent 1px, transparent 7px
    );
  }
  .id-card-person { display: grid; grid-template-columns: 58px minmax(0, 1fr); gap: 0.45rem; align-content: start; min-width: 0; }
  .id-card-photo {
    width: 58px; height: 70px; border-radius: 8px; border: 2px solid var(--id-card-teal);
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.18); background: #f8fafc; overflow: hidden;
    display: grid; place-items: center; font-weight: 900; color: var(--id-card-teal); position: relative; z-index: 1;
  }
  .id-card-photo img { width: 100%; height: 100%; object-fit: cover; }
  .id-card-person p { margin: 0.02rem 0 0.24rem; font-size: 0.72rem; line-height: 1.05; font-weight: 900; overflow-wrap: anywhere; }
  .id-card-person strong { display: inline-flex; max-width: 100%; background: #e7f7ef; color: #0d6b3f; border-radius: 7px; padding: 0.16rem 0.32rem; font-size: 0.52rem; overflow-wrap: anywhere; }
  .id-card-person span { display: block; color: #475569; font-weight: 800; margin-top: 0.24rem; font-size: 0.55rem; overflow-wrap: anywhere; }

  .id-card-details { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.18rem; align-content: start; margin: 0; }
  .id-card-details div { border: 1px solid #e2e8f0; background: #f8fafc; border-radius: 6px; padding: 0.16rem 0.22rem; min-width: 0; }
  .id-card-details dt { color: var(--id-card-muted); text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.38rem; font-weight: 900; margin: 0; }
  .id-card-details dd { margin: 0.04rem 0 0; font-size: 0.46rem; line-height: 1.05; font-weight: 800; overflow-wrap: anywhere; }

  .id-card-footer {
    display: grid; grid-template-columns: 74px 1fr; gap: 0.5rem; align-items: center;
    margin: 0 0.62rem 0.42rem; padding: 0.26rem 0.42rem; border-radius: 7px;
    background: var(--doc-secondary, #0f172a); color: #ffffff; position: relative; z-index: 1;
  }
  .id-card-front-footer { display: block; }
  .id-card-footer strong, .id-card-footer span { display: block; }
  .id-card-footer span { color: #cbd5e1; font-size: 0.48rem; line-height: 1.12; overflow-wrap: anywhere; }

  .id-card-signature-block { display: grid; justify-items: center; gap: 2px; margin: 0 0.62rem 0.5rem; }
  .id-card-signature-img { height: 34px; max-width: 130px; object-fit: contain; }
  .id-card-signature-block span { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; font-weight: 800; }

  .id-card-back-body { display: grid; grid-template-columns: minmax(72px, 0.8fr) 1fr; gap: 0.4rem; align-items: start; padding: 0.3rem 0.55rem; }
  .id-card-back-qr-panel { display: grid; align-content: start; justify-items: center; text-align: center; }
  .id-card-back-qr-panel p { margin: 0 0 0.18rem; color: var(--id-card-muted); text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.42rem; font-weight: 900; }
  .id-card-back-qr { width: 74px; height: 74px; border-radius: 8px; background: #ffffff; border: 1px solid var(--id-card-line); padding: 0.2rem; display: grid; place-items: center; color: var(--id-card-teal); font-weight: 900; }
  .id-card-back-qr img { width: 100%; height: 100%; object-fit: contain; }
  .id-card-back-qr-panel > strong { display: inline-flex; max-width: 100%; margin-top: 0.2rem; padding: 0.14rem 0.36rem; border-radius: 7px; background: #e7f7ef; color: #0d6b3f; font-size: 0.44rem; overflow-wrap: anywhere; }
  .id-card-back-qr-panel > span { margin-top: 0.14rem; font-size: 0.5rem; line-height: 1.05; font-weight: 900; overflow-wrap: anywhere; color: var(--id-card-ink); }

  .id-card-back-return { display: grid; gap: 0.16rem; font-size: 0.44rem; line-height: 1.22; color: var(--id-card-ink); align-content: start; }
  .id-card-back-return-lead { margin: 0; font-weight: 800; }
  .id-card-back-address { margin: 0; font-style: normal; white-space: pre-line; color: var(--id-card-muted); }
  .id-card-back-phone { margin: 0; font-weight: 800; }
  .id-card-back-email { margin: 0; font-weight: 600; color: var(--id-card-muted); }
  .id-card-back-validity { margin: 0.1rem 0 0; color: var(--id-card-muted); font-size: 0.4rem; line-height: 1.2; }

  .id-card-powered-by { margin: 0; padding: 0.1rem 0 0.2rem; text-align: center; color: var(--id-card-muted); font-size: 0.38rem; letter-spacing: 0.03em; }
  .id-card-back .id-card-powered-by { border-top: 1px solid var(--id-card-line); }
"""


def _logo_html(brand):
    if brand.get("logo"):
        return f'<img src="{escape(brand["logo"])}" alt="">'
    return f'<span>{escape(brand.get("initials") or "SD")}</span>'


def _front_face_html(person, brand):
    photo_html = (
        f'<img src="{escape(person["profile_picture"])}" alt="">'
        if person.get("profile_picture")
        else f'<span>{escape(_initials(person.get("name")))}</span>'
    )
    motto_html = f'<small class="id-card-motto">{escape(brand["motto"])}</small>' if brand.get("motto") else ""
    # Class dropped from the student card per school policy, same as
    # IdCardFaces - staff still show their role/specialization here.
    is_student = person.get("person_type") == "student"
    sub_label = person.get("secondary_label") if is_student else person.get("primary_label")
    sub_label_html = f"<span>{escape(sub_label)}</span>" if sub_label else ""
    details_html = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>" for label, value in _detail_rows(person)
    )
    return f"""
<div class="id-card-page id-card-preview-card id-card-front">
  <div class="id-card-ribbon">{escape(person.get("display_type") or "")}</div>
  <header class="id-card-top">
    <div class="id-card-school-logo">{_logo_html(brand)}</div>
    <div>
      <strong>{escape(brand["name"])}</strong>
      {motto_html}
      <span>{escape(brand.get("code") or "Official Identity Card")}</span>
    </div>
  </header>
  <section class="id-card-front-body">
    <section class="id-card-person">
      <div class="id-card-photo">{photo_html}</div>
      <div>
        <p>{escape(person.get("name") or "Unnamed user")}</p>
        <strong>{escape(person.get("unique_id") or "No ID assigned")}</strong>
        {sub_label_html}
      </div>
    </section>
    <dl class="id-card-details">{details_html}</dl>
  </section>
  <footer class="id-card-footer id-card-front-footer">
    <strong><span>{escape(brand.get("email") or "SchoolDom profile verification")}</span></strong>
  </footer>
  <p class="id-card-powered-by">Powered by Schooldom</p>
</div>
"""


def _back_face_html(person, brand, qr_data_url):
    motto_html = f'<small class="id-card-motto">{escape(brand["motto"])}</small>' if brand.get("motto") else ""
    qr_html = f'<img src="{qr_data_url}" alt="">' if qr_data_url else "<span>QR</span>"
    address_html = f'<address class="id-card-back-address">{escape(brand["address"])}</address>' if brand.get("address") else ""
    phone_html = f'<p class="id-card-back-phone">Tel: {escape(brand["phone"])}</p>' if brand.get("phone") else ""
    email_html = f'<p class="id-card-back-email">{escape(brand["email"])}</p>' if brand.get("email") else ""
    signature_html = ""
    if brand.get("signature"):
        signature_html = f"""
  <div class="id-card-signature-block">
    <img src="{escape(brand["signature"])}" alt="" class="id-card-signature-img">
    <span>Authorized Signature</span>
  </div>"""
    return f"""
<div class="id-card-page id-card-preview-card id-card-back">
  <header class="id-card-back-head">
    <div class="id-card-school-logo">{_logo_html(brand)}</div>
    <div>
      <strong>{escape(brand["name"])}</strong>
      {motto_html}
      <span>Official ID verification</span>
    </div>
  </header>
  <section class="id-card-back-body">
    <div class="id-card-back-qr-panel">
      <p>Scan to verify</p>
      <div class="id-card-back-qr">{qr_html}</div>
      <strong>{escape(person.get("unique_id") or "No ID assigned")}</strong>
      <span>{escape(person.get("name") or "Unnamed user")}</span>
    </div>
    <div class="id-card-back-return">
      <p class="id-card-back-return-lead">If found please return to the following address or call the number below:</p>
      {address_html}
      {phone_html}
      {email_html}
      <p class="id-card-back-validity">Valid only when the scan page confirms this profile as verified and active.</p>
    </div>
  </section>
  {signature_html}
  <p class="id-card-powered-by">Powered by Schooldom</p>
</div>
"""


def _document_html(person, brand, theme):
    theme = theme or {}
    teal = _safe_css_color(theme.get("accent_color"), "#0f3d5e")
    green = _safe_css_color(theme.get("primary_color"), "#0f8a55")
    secondary = _safe_css_color(theme.get("secondary_color"), "#0f172a")
    font_family = _safe_font_family(theme.get("font_family"))
    qr_data_url = person.pop("_qr_data_url", "")
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root {{
    --id-card-ink: #102033; --id-card-muted: #64748b; --id-card-line: #dbe5f0;
    --id-card-teal: {teal}; --id-card-green: {green}; --doc-secondary: {secondary};
    --doc-font-family: "{font_family}";
  }}
  {_CARD_CSS}
</style>
</head>
<body>
{_front_face_html(person, brand)}
{_back_face_html(person, brand, qr_data_url)}
</body>
</html>"""


def generate_id_cards_zip(people, brand, theme, qr_data_urls):
    """people: list of payload dicts from _resolve_id_card_person.
    qr_data_urls: dict keyed by "{person_type}:{id}" -> a data: URL string
    (possibly "" if that person's QR couldn't be generated).
    Returns (zip_bytes, exported_count). Raises on a browser-level failure -
    callers should turn that into a clean error response, same as any other
    external-dependency failure."""
    from playwright.sync_api import sync_playwright

    buffer = io.BytesIO()
    exported = 0
    used_names = set()
    with sync_playwright() as pw:
        # --no-sandbox: this runs as root on the production host, where
        # Chromium's own sandbox refuses to initialize without it - see
        # https://github.com/microsoft/playwright/issues (standard
        # server/Docker guidance, not specific to this app).
        browser = pw.chromium.launch(args=["--no-sandbox"])
        try:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                for index, person in enumerate(people):
                    key = f'{person["person_type"]}:{person["id"]}'
                    person = dict(person, _qr_data_url=qr_data_urls.get(key, ""))
                    html_doc = _document_html(person, brand, theme)
                    page = browser.new_page()
                    try:
                        page.set_content(html_doc, wait_until="networkidle")
                        pdf_bytes = page.pdf(
                            width=f"{CARD_WIDTH_IN}in",
                            height=f"{CARD_HEIGHT_IN}in",
                            print_background=True,
                            margin={"top": "0in", "right": "0in", "bottom": "0in", "left": "0in"},
                        )
                    finally:
                        page.close()

                    base_name = sanitize_filename(
                        f'{person.get("name") or "ID Card"} - {person.get("unique_id") or person["id"]}'
                    ) or f"id-card-{index + 1}"
                    file_name = f"{base_name}.pdf"
                    suffix = 2
                    while file_name in used_names:
                        file_name = f"{base_name} ({suffix}).pdf"
                        suffix += 1
                    used_names.add(file_name)
                    zf.writestr(file_name, pdf_bytes)
                    exported += 1
        finally:
            browser.close()
    return buffer.getvalue(), exported
