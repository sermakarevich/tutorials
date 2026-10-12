"""Screenshots for chapter 02 that need a click (a tab whose URL has no direct path).

Reuses the same login flow as screenshots.py; never edits it.
Run from project/: uv run python -m openmetadata_tutorial.ch02_screens
"""

from playwright.sync_api import sync_playwright

from openmetadata_tutorial.config import project_root, settings


def _login(page, s):
    page.goto(f"{s.om_url}/signin")
    page.fill("#email", s.om_admin_email)
    page.fill("#password", s.om_admin_password)
    page.click("button[type=submit]")
    page.wait_for_url(lambda u: "/signin" not in u, timeout=60_000)


def capture_tab(path: str, tab: str, out: str, wait_text: str | None = None, full: bool = False) -> str:
    """Open a table page, click the tab named `tab`, and screenshot it."""
    s = settings()
    target = project_root().parent / out
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _login(page, s)
        page.goto(f"{s.om_url}{path}")
        page.wait_for_load_state("networkidle")
        page.get_by_text(tab, exact=True).first.click()
        page.wait_for_load_state("networkidle")
        if wait_text:
            page.get_by_text(wait_text).first.wait_for(timeout=30_000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(target), full_page=full)
        browser.close()
    print("saved", target)
    return str(target)


def capture_versions(path: str, out: str) -> str:
    """Open a table page, click the version button (top right), screenshot the history."""
    s = settings()
    target = project_root().parent / out
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _login(page, s)
        page.goto(f"{s.om_url}{path}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
        # The version button shows the current version, e.g. "0.3", top right.
        current = get_version(path)
        page.get_by_text(current, exact=True).first.click()
        page.wait_for_timeout(2500)
        page.screenshot(path=str(target), full_page=False)
        browser.close()
    print("saved", target)
    return str(target)


def get_version(fqn_path: str) -> str:
    """Read the current entity version, e.g. '0.3', via the API."""
    from openmetadata_tutorial.client import get

    fqn = fqn_path.split("/table/")[-1]
    return str(get(f"/v1/tables/name/{fqn}", fields="version")["version"])


def capture_lineage(path: str, out: str) -> str:
    """Open a Lineage tab, hide the minimap, zoom out, pan, and screenshot."""
    s = settings()
    target = project_root().parent / out
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _login(page, s)
        page.goto(f"{s.om_url}{path}")
        page.wait_for_load_state("networkidle")
        page.get_by_text("fct_orders").first.wait_for(timeout=30_000)
        page.wait_for_timeout(2000)
        page.get_by_label("Mind Map").click(timeout=10_000)
        page.get_by_label("Zoom Out").click(timeout=10_000)
        page.get_by_label("Zoom Out").click(timeout=10_000)
        page.wait_for_timeout(1000)
        page.mouse.move(700, 600)
        page.mouse.down()
        page.mouse.move(880, 600, steps=10)
        page.mouse.up()
        page.wait_for_timeout(1000)
        page.screenshot(path=str(target), full_page=False)
        browser.close()
    print("saved", target)
    return str(target)


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    from openmetadata_tutorial.config import settings as _settings

    # Data Observability -> Data Quality sub-tab, showing the failed tests.
    s = _settings()
    target = project_root().parent / "assets/02_quality_orders.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _login(page, s)
        page.goto(f"{s.om_url}/table/brightcup_pg.brightcup.raw.orders")
        page.wait_for_load_state("networkidle")
        page.get_by_text("Data Observability", exact=True).first.click()
        page.wait_for_load_state("networkidle")
        page.get_by_text("Data Quality", exact=True).first.click()
        page.wait_for_load_state("networkidle")
        page.get_by_text("Failed").first.wait_for(timeout=30_000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(target), full_page=True)
        browser.close()
    print("saved", target)
    # Customers Columns tab (the default tab): scroll to the PII-tagged rows.
    target = project_root().parent / "assets/02_customers_pii.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _login(page, s)
        page.goto(f"{s.om_url}/table/brightcup_pg.brightcup.raw.customers")
        page.wait_for_load_state("networkidle")
        page.get_by_text("full_name").first.wait_for(timeout=30_000)
        page.get_by_text("full_name").first.scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(target), full_page=False)
        browser.close()
    print("saved", target)
    capture_versions(
        "/table/brightcup_pg.brightcup.raw.products",
        "assets/02_products_versions.png",
    )
    capture_lineage(
        "/table/brightcup_pg.brightcup.analytics.daily_revenue/lineage",
        "assets/02_lineage_daily_revenue.png",
    )
