"""axe-core integration for accessibility scanning.

axe-core is the rules engine most accessibility tools are built on, including
the browser extensions and the scanners inside commercial products. It is a
JavaScript library, so Northline injects it into the page and runs it there.

Why inject the library rather than use a Python wrapper: the version is pinned
in package.json and visible in the report, the options passed to axe.run are
explicit rather than hidden behind someone else's defaults, and there is one
fewer dependency whose behaviour has to be trusted.

WHAT AUTOMATED SCANNING CAN AND CANNOT DO

axe-core's own documentation is clear that automated testing finds a minority
of accessibility barriers. Roughly a third is the commonly cited figure. It
reliably catches machine-checkable rules: a form input with no associated
label, insufficient colour contrast, a missing page language, an image with no
alternative text.

It cannot judge whether alternative text is meaningful, whether a focus
indicator is actually perceivable, whether the tab order matches the visual
order, or whether an error message makes sense to someone who cannot see the
field it refers to. Those need a person, which is why TC-ACC-005 and TC-ACC-006
are manual.

A passing axe scan is therefore NOT evidence of WCAG conformance, and Northline
does not claim it is. See docs/accessibility-report.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
AXE_SOURCE = REPO_ROOT / "node_modules" / "axe-core" / "axe.min.js"

#: WCAG 2.1 level AA, which is the standard named in REQ-ACC-001 and the level
#: required under the Accessibility for Ontarians with Disabilities Act.
WCAG_21_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]

#: Impact levels that fail the gate. axe reports minor and moderate as well,
#: and those are recorded in the report but do not fail the build, matching
#: GATE-ACCESSIBILITY in quality-gates.yaml.
FAILING_IMPACTS = ("critical", "serious")


class AxeNotInstalled(RuntimeError):
    pass


def axe_script() -> str:
    if not AXE_SOURCE.exists():
        raise AxeNotInstalled(
            f"axe-core not found at {AXE_SOURCE}. Run: npm install"
        )
    return AXE_SOURCE.read_text(encoding="utf-8")


def axe_version() -> str:
    """Read the installed version so every report states which rules ran."""
    import json
    package = AXE_SOURCE.parent / "package.json"
    return json.loads(package.read_text())["version"] if package.exists() else "unknown"


def run_axe(page, tags: list[str] | None = None) -> dict[str, Any]:
    """Inject axe-core into the current page and run it.

    Returns axe's raw result: violations, passes, incomplete and inapplicable.
    The raw shape is kept rather than simplified, because 'incomplete' is the
    category axe uses for checks it could not decide automatically, and those
    are exactly the ones a person has to review.
    """
    page.add_script_tag(content=axe_script())
    return page.evaluate(
        """async (tags) => await axe.run(document, {
             runOnly: { type: 'tag', values: tags },
             resultTypes: ['violations', 'incomplete']
           })""",
        tags or WCAG_21_AA_TAGS,
    )


def violations(result: dict[str, Any], impacts: tuple[str, ...] | None = None) -> list[dict]:
    """Violations, optionally filtered to particular impact levels."""
    found = result.get("violations", [])
    if impacts is None:
        return found
    return [v for v in found if v.get("impact") in impacts]


def summarise(result: dict[str, Any]) -> dict[str, int]:
    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0, "unknown": 0}
    for violation in result.get("violations", []):
        impact = violation.get("impact") or "unknown"
        counts[impact] = counts.get(impact, 0) + 1
    return counts


def describe(result: dict[str, Any], impacts: tuple[str, ...] | None = None) -> str:
    """A readable breakdown, used in failure messages and in the report.

    Each violation names the rule, the impact, the WCAG success criteria it maps
    to, and the elements involved. A failure message that says only
    'accessibility violations found' sends someone hunting.
    """
    lines: list[str] = []
    for violation in violations(result, impacts):
        wcag = [t for t in violation.get("tags", []) if t.startswith("wcag")]
        lines.append(
            f"  [{violation.get('impact')}] {violation.get('id')}: {violation.get('help')}"
        )
        lines.append(f"      success criteria: {', '.join(wcag) or 'none stated'}")
        lines.append(f"      help: {violation.get('helpUrl', 'none')}")
        for node in violation.get("nodes", [])[:5]:
            target = ", ".join(str(t) for t in node.get("target", []))
            snippet = " ".join((node.get("html") or "").split())[:120]
            lines.append(f"      element: {target}")
            lines.append(f"        html: {snippet}")
        remaining = len(violation.get("nodes", [])) - 5
        if remaining > 0:
            lines.append(f"      ... and {remaining} more element(s)")
        lines.append("")
    return "\n".join(lines) if lines else "  none"
