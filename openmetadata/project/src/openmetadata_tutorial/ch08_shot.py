"""Chapter 08 screenshot: the governed daily_revenue page with the glossary term visible.

Why this exists instead of `just shot`: the columns table is wider than its
card (1200px of columns in an 844px scroller, observed) and the Glossary
Terms column — with the `Revenue` pill on the `revenue` row — sits ~140px
past the visible right edge at 1440x900. Playwright's `full_page` only grows
the document, not inner scrollers (a `--full` shot comes back exactly
1440x900), so the term needs the table scrolled right. This helper repeats
the standard admin login, scrolls the table until the
`tag-Brightcup.Revenue` pill is in view (vertical position untouched, so the
owner/tier/certification/domain header stays put), and saves a viewport shot.

Run from project/: uv run python -m openmetadata_tutorial.ch08_shot
"""

from playwright.sync_api import sync_playwright

from openmetadata_tutorial.config import project_root, settings

FQN = "brightcup_pg.brightcup.analytics.daily_revenue"
OUT = "assets/08_daily_revenue_governed.png"
PILL = '[data-testid="tag-Brightcup.Revenue"]'


def capture() -> str:
    s = settings()
    target = project_root().parent / OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{s.om_url}/signin")
        page.fill("#email", s.om_admin_email)
        page.fill("#password", s.om_admin_password)
        page.click("button[type=submit]")
        page.wait_for_url(lambda u: "/signin" not in u, timeout=60_000)
        page.goto(f"{s.om_url}/table/{FQN}")
        page.wait_for_load_state("networkidle")
        page.locator(PILL).first.wait_for(timeout=30_000)
        page.wait_for_timeout(1500)  # let tags render
        # Horizontal-only scroll: bring the pill ~30px inside the visible
        # right edge of the table scroller; never touch vertical scroll.
        box = page.evaluate(
            """(sel) => {
              const pill = document.querySelector(sel);
              const sc = pill.closest('.ant-table-content');
              const sr = sc.getBoundingClientRect(), pr = pill.getBoundingClientRect();
              sc.scrollLeft = pr.right - sr.right + sc.scrollLeft + 30;
              const after = pill.getBoundingClientRect();
              return {pill: [after.x, after.y, after.width, after.height],
                      scroller: [sr.x, sr.y, sr.width, sr.height]};
            }""",
            PILL,
        )
        page.wait_for_timeout(500)
        page.screenshot(path=str(target), full_page=False)
        browser.close()
    return f"saved {target} pill={box['pill']} scroller={box['scroller']}"


if __name__ == "__main__":
    print(capture())
