"""Automated accessibility scanning with axe-core.

Covers TC-ACC-001 to TC-ACC-004 and TC-ACC-007.

Two kinds of test here, and the difference matters.

The requirement tests assert what REQ-ACC-001 and REQ-ACC-002 actually demand:
no critical or serious violations, and a label on every form input. ParaBank
fails both, so they are marked as known defects referencing DEF-003 and DEF-004.

The regression tests assert that no NEW rule starts failing. Those pass today
and are the ones that would catch a change for the worse. Asserting perfection
against a known-imperfect application produces a permanently red suite that
everybody learns to ignore; asserting "no worse than the recorded baseline"
keeps the check alive.
"""

from __future__ import annotations

import pytest

from utils.accessibility import FAILING_IMPACTS, describe, run_axe, summarise, violations
from utils.config import Settings

pytestmark = pytest.mark.accessibility

#: Rules observed failing on 2026-08-31 with axe-core 4.13.0, recorded in
#: docs/accessibility-report.md. A rule appearing that is not in this set is a
#: new accessibility regression and fails the build.
BASELINE = {
    "login": {"image-alt", "label", "color-contrast", "html-has-lang", "link-name"},
    "register": {"image-alt", "label", "color-contrast", "html-has-lang", "link-name"},
    "overview": {"image-alt", "color-contrast", "html-has-lang", "link-name"},
    "transfer": {"image-alt", "label", "select-name", "color-contrast",
                 "html-has-lang", "link-name"},
    "billpay": {"image-alt", "label", "select-name", "color-contrast",
                "html-has-lang", "link-name"},
}

PUBLIC_PAGES = {"login": "/index.htm", "register": "/register.htm"}
PRIVATE_PAGES = {"overview": "/overview.htm", "transfer": "/transfer.htm",
                 "billpay": "/billpay.htm"}

DEF_003 = (
    "DEF-003: form inputs and select elements have no accessible name on the "
    "login, registration, transfer and bill payment pages. A screen reader user "
    "cannot tell what any field is for. Confirmed 2026-08-31 with axe-core "
    "4.13.0: 25 unlabelled form elements and 3 unnamed selects across four "
    "pages. Marked strict so this fails if the application is fixed without the "
    "tests being updated."
)

DEF_004 = (
    "DEF-004: page-level accessibility failures present on every page — no lang "
    "attribute on the html element, an image with no alternative text, a link "
    "with no discernible text, and colour contrast below the WCAG 2.1 AA "
    "threshold. Confirmed 2026-08-31 with axe-core 4.13.0."
)


@pytest.fixture
def scan(page, base_url: str, settings: Settings):
    """Open a page, logging in first when it needs a session, and run axe."""
    def _scan(key: str) -> dict:
        if key in PUBLIC_PAGES:
            page.goto(f"{base_url}{PUBLIC_PAGES[key]}")
        else:
            page.goto(f"{base_url}/index.htm")
            page.fill("input[name='username']", settings.sut.username)
            page.fill("input[name='password']", settings.sut.password)
            page.click("input[type='submit'][value='Log In']")
            page.wait_for_load_state("networkidle")
            page.goto(f"{base_url}{PRIVATE_PAGES[key]}")
        page.wait_for_load_state("networkidle")
        return run_axe(page)
    return _scan


# --- regression guards: these pass today ------------------------------------

@pytest.mark.parametrize("page_key", sorted(BASELINE))
def test_no_new_accessibility_rule_starts_failing(scan, page_key: str):
    """REQ-ACC-001, regression form.

    The application already fails several rules, recorded in BASELINE. This
    asserts no rule outside that set begins failing, which is the change that
    would represent an accessibility regression rather than the existing state.
    """
    result = scan(page_key)
    failing = {v["id"] for v in result.get("violations", [])}
    new = failing - BASELINE[page_key]
    assert not new, (
        f"New accessibility rule(s) failing on the {page_key} page: {sorted(new)}\n"
        + describe(result)
    )


@pytest.mark.parametrize("page_key", sorted(BASELINE))
def test_the_scan_runs_and_returns_a_usable_result(scan, page_key: str):
    """REQ-ACC-001. Confirms axe actually executed rather than silently failing.

    A scanner that errors and returns nothing looks identical to a clean page.
    """
    result = scan(page_key)
    assert "violations" in result, f"axe returned no violations key for {page_key}"
    assert result.get("testEngine", {}).get("version"), "axe did not report its version"
    counts = summarise(result)
    print(f"{page_key}: {counts}, needs review: {len(result.get('incomplete', []))}")


# --- requirement assertions: these fail, and are recorded as defects ---------

@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason=DEF_003 + " " + DEF_004)
@pytest.mark.parametrize("page_key", sorted(BASELINE))
def test_key_pages_have_no_critical_or_serious_violations(scan, page_key: str):
    """TC-ACC-001, TC-ACC-002 and TC-ACC-003 / REQ-ACC-001, as the requirement states it."""
    result = scan(page_key)
    failing = violations(result, FAILING_IMPACTS)
    assert not failing, (
        f"{page_key} page has {len(failing)} critical or serious violation(s):\n"
        + describe(result, FAILING_IMPACTS)
    )


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=DEF_003)
@pytest.mark.parametrize("page_key", ["login", "register", "transfer", "billpay"])
def test_every_form_input_has_an_accessible_name(scan, page_key: str):
    """TC-ACC-004 / REQ-ACC-002.

    The narrowest and most consequential of the findings. A visible caption that
    is not associated in the markup does not count: assistive technology reads
    the association, not the visual layout.

    Predicted in Phase 3C from the markup alone. docs/sut-ui-elements.md
    Finding 5 noted that the login inputs carry no id, so no label could
    reference them, which is why Playwright's get_by_label was unusable. This
    confirms it against the accessibility rules engine.
    """
    result = scan(page_key)
    naming = [v for v in result.get("violations", [])
              if v["id"] in ("label", "select-name", "form-field-multiple-labels")]
    elements = sum(len(v.get("nodes", [])) for v in naming)
    assert not naming, (
        f"{page_key} page has {elements} form element(s) with no accessible name:\n"
        + describe(result)
    )
