"""Real UI screenshots for the chapters (headless Chromium via Playwright).

`python -m openmetadata_tutorial.screenshots <url-path> <out.png> [--wait-text TEXT] [--full]`
logs in as the admin user, opens http://localhost:18585<url-path>, waits for the page
(and optionally for TEXT to appear), and saves a 1440x900 PNG. Output paths are
relative to the tutorial folder (the parent of project/), e.g. assets/02_explore.png.
One-time setup: `uv run playwright install chromium`.
"""

import argparse

from playwright.sync_api import sync_playwright

from openmetadata_tutorial.config import project_root, settings


def capture(path: str, out: str, wait_text: str | None = None, full: bool = False) -> str:
    s = settings()
    target = project_root().parent / out
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{s.om_url}/signin")
        page.fill("#email", s.om_admin_email)
        page.fill("#password", s.om_admin_password)
        page.click("button[type=submit]")
        page.wait_for_url(lambda u: "/signin" not in u, timeout=60_000)
        page.goto(f"{s.om_url}{path}")
        page.wait_for_load_state("networkidle")
        if wait_text:
            page.get_by_text(wait_text).first.wait_for(timeout=30_000)
        page.wait_for_timeout(1500)  # let charts and lineage canvases finish drawing
        page.screenshot(path=str(target), full_page=full)
        browser.close()
    return str(target)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("path")
    a.add_argument("out")
    a.add_argument("--wait-text")
    a.add_argument("--full", action="store_true")
    ns = a.parse_args()
    print("saved", capture(ns.path, ns.out, ns.wait_text, ns.full))
