"""Scan ParaBank's key pages with axe-core and write the accessibility report.

Runs before the accessibility tests are written, so that the assertions are
based on what the application actually does rather than on what it might do.
Same discovery-first approach used for the endpoints, the API shapes and the
page structure.

Writes:
    reports/accessibility-scan.json   the raw axe output, per page
    docs/accessibility-report.md      the readable report

Exit code is always 0. This is a scan, not a gate. The gate lives in the tests.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from utils.accessibility import (  # noqa: E402
    FAILING_IMPACTS,
    WCAG_21_AA_TAGS,
    axe_version,
    run_axe,
    summarise,
)
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("scan_accessibility")

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT = REPO_ROOT / "docs" / "accessibility-report.md"


def render_page_section(name: str, path: str, result: dict) -> list[str]:
    counts = summarise(result)
    total = sum(counts.values())
    lines = [
        f"## {name}",
        "",
        f"    path:       {path}",
        f"    violations: {total}",
        f"    critical {counts['critical']}   serious {counts['serious']}   "
        f"moderate {counts['moderate']}   minor {counts['minor']}",
        f"    needs review (axe could not decide): {len(result.get('incomplete', []))}",
        "",
    ]

    if not result.get("violations"):
        lines += ["No automated violations found on this page.", ""]
        return lines

    lines += ["| Impact | Rule | Success criteria | Elements | Description |",
              "| --- | --- | --- | --- | --- |"]
    for violation in sorted(result["violations"],
                            key=lambda v: (v.get("impact") or "zzz")):
        wcag = ", ".join(t for t in violation.get("tags", []) if t.startswith("wcag"))
        lines.append(
            f"| {violation.get('impact')} | `{violation.get('id')}` | {wcag or '-'} | "
            f"{len(violation.get('nodes', []))} | {violation.get('help')} |"
        )
    lines.append("")

    lines += ["Affected elements:", "", "```"]
    for violation in result["violations"]:
        lines.append(f"{violation.get('id')} ({violation.get('impact')})")
        for node in violation.get("nodes", [])[:6]:
            snippet = " ".join((node.get("html") or "").split())[:110]
            lines.append(f"    {snippet}")
        remaining = len(violation.get("nodes", [])) - 6
        if remaining > 0:
            lines.append(f"    ... and {remaining} more")
        lines.append("")
    lines += ["```", ""]
    return lines


def main() -> int:
    settings = get_settings()
    base = settings.sut.base_url
    version = axe_version()
    log.info("axe-core version %s, tags %s", version, ", ".join(WCAG_21_AA_TAGS))

    raw: dict[str, dict] = {}
    sections: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15000)

        log.info("Scanning the login page")
        page.goto(f"{base}/index.htm")
        page.wait_for_load_state("networkidle")
        raw["login"] = run_axe(page)
        sections += render_page_section("Login page", "/index.htm", raw["login"])

        log.info("Scanning the registration page")
        page.goto(f"{base}/register.htm")
        page.wait_for_load_state("networkidle")
        raw["register"] = run_axe(page)
        sections += render_page_section("Registration page", "/register.htm", raw["register"])

        log.info("Logging in")
        page.goto(f"{base}/index.htm")
        page.fill("input[name='username']", settings.sut.username)
        page.fill("input[name='password']", settings.sut.password)
        page.click("input[type='submit'][value='Log In']")
        page.wait_for_load_state("networkidle")

        for label, path, key in [
            ("Account overview", "/overview.htm", "overview"),
            ("Transfer funds", "/transfer.htm", "transfer"),
            ("Bill payment", "/billpay.htm", "billpay"),
        ]:
            log.info("Scanning %s", label)
            page.goto(f"{base}{path}")
            page.wait_for_load_state("networkidle")
            raw[key] = run_axe(page)
            sections += render_page_section(label, path, raw[key])

        browser.close()

    totals = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    for result in raw.values():
        for impact, count in summarise(result).items():
            if impact in totals:
                totals[impact] += count

    header = [
        "# Accessibility report",
        "",
        f"Generated by scripts/scan_accessibility.py on "
        f"{datetime.now(tz=timezone.utc).date().isoformat()}.",
        "Do not edit by hand. Re-run the script instead.",
        "",
        f"    axe-core version: {version}",
        f"    rule tags:        {', '.join(WCAG_21_AA_TAGS)}",
        f"    standard:         WCAG 2.1 level AA",
        f"    browser:          Chromium",
        f"    pages scanned:    {len(raw)}",
        "",
        "## Totals across all pages",
        "",
        "| Impact | Count |",
        "| --- | --- |",
        f"| critical | {totals['critical']} |",
        f"| serious | {totals['serious']} |",
        f"| moderate | {totals['moderate']} |",
        f"| minor | {totals['minor']} |",
        "",
        f"GATE-ACCESSIBILITY fails on any violation of impact "
        f"{' or '.join(FAILING_IMPACTS)}.",
        "",
        "## What this report does NOT say",
        "",
        "It does not say ParaBank conforms to WCAG 2.1 level AA, and a clean result",
        "here would not say that either.",
        "",
        "Automated scanning finds the machine-checkable subset of accessibility",
        "barriers, commonly estimated at around a third of the real total. axe-core",
        "reliably detects a form input with no associated label, insufficient colour",
        "contrast, a missing page language, an image with no alternative text.",
        "",
        "It cannot judge whether alternative text is meaningful, whether a focus",
        "indicator is actually perceivable, whether tab order follows the visual",
        "order, or whether an error message makes sense to somebody who cannot see",
        "the field it refers to. Those require a person, which is why TC-ACC-005 and",
        "TC-ACC-006 are manual and their results are recorded separately below.",
        "",
        "The 'needs review' count on each page is axe's own 'incomplete' category:",
        "checks it could not decide automatically. Those are candidates for manual",
        "review, not passes.",
        "",
    ]

    REPORT.write_text("\n".join(header + sections))
    (settings.reports_dir / "accessibility-scan.json").write_text(json.dumps(raw, indent=2))

    log.info("Totals: critical %d, serious %d, moderate %d, minor %d",
             totals["critical"], totals["serious"], totals["moderate"], totals["minor"])
    log.info("Wrote %s", REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
