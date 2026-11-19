"""HTML to PDF for the public receipt, report-card and statement pages.

Uses the same headless Chromium (Playwright) the ID-card export uses, so there is
no new dependency on the server. Raises on a browser-level failure; callers turn
that into a clean error response or a skipped send.
"""


def render_html_to_pdf(html_document: str) -> bytes:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        # --no-sandbox: runs as root on the production host, where Chromium's own
        # sandbox refuses to start (same reason as users/id_card_pdf.py).
        browser = pw.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page()
            try:
                page.set_content(html_document, wait_until="networkidle")
                return page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "12mm", "right": "10mm", "bottom": "12mm", "left": "10mm"},
                )
            finally:
                page.close()
        finally:
            browser.close()
