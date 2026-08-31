"""Visual regression comparison.

The Python binding of Playwright has no to_have_screenshot assertion. That
exists only in the JavaScript binding, so the comparison is implemented here.

The approach is deliberately simple and explainable:

  1. Take a screenshot.
  2. If no baseline exists, write one and fail, saying a baseline was created.
     Silently accepting the first screenshot as correct would mean the very
     first run can never fail, which defeats the purpose.
  3. If a baseline exists, compare pixel by pixel and fail if the proportion of
     differing pixels exceeds the tolerance.
  4. On failure, write the actual image and a difference image to
     reports/artifacts/visual/ so the change can be seen rather than guessed at.

Two tolerances, because a single one cannot express what matters:

  CHANNEL_THRESHOLD  how different one pixel must be before it counts as
                     changed at all. Anti-aliasing on text edges moves values
                     by a few units between runs, and treating that as a
                     regression makes the suite untrustworthy.
  tolerance_ratio    what proportion of changed pixels is acceptable overall.
                     Defaults to zero: for a static page, any real change
                     should fail.

Baselines are stored per browser, because Chromium, Firefox and WebKit render
fonts and form controls differently. A baseline from one is not valid for
another.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DIR = REPO_ROOT / "tests" / "ui" / "baselines"
DIFF_DIR = REPO_ROOT / "reports" / "artifacts" / "visual"


def platform_key() -> str:
    """Baselines are per operating system as well as per browser.

    Font rendering, form control styling and sub-pixel antialiasing all differ
    between macOS, Linux and Windows. A baseline captured on one will never
    match a screenshot taken on another, and the failure looks like a layout
    regression when it is only a different machine.

    Including the platform in the path makes that impossible to get wrong
    silently: a run on a platform with no baselines creates its own rather than
    comparing against somebody else's.
    """
    return sys.platform

#: How far one colour channel must move before the pixel counts as changed.
CHANNEL_THRESHOLD = 24


def _update_requested() -> bool:
    return os.getenv("NORTHLINE_UPDATE_BASELINES", "").strip().lower() in ("1", "true", "yes")


def changed_pixel_ratio(baseline: Path, actual: Path, diff_out: Path | None = None) -> float:
    """Proportion of pixels that differ meaningfully between two images."""
    with Image.open(baseline) as a, Image.open(actual) as b:
        first = a.convert("RGB")
        second = b.convert("RGB")

        if first.size != second.size:
            raise AssertionError(
                f"Image sizes differ: baseline {first.size}, actual {second.size}. "
                "A layout change, or a different viewport size between runs."
            )

        difference = ImageChops.difference(first, second)
        if diff_out is not None:
            diff_out.parent.mkdir(parents=True, exist_ok=True)
            difference.save(diff_out)

        # Reduce to a single channel holding the largest change at each pixel,
        # then count the pixels above the threshold using the histogram.
        flattened = difference.convert("L")
        histogram = flattened.histogram()
        changed = sum(histogram[CHANNEL_THRESHOLD:])
        total = first.size[0] * first.size[1]
        return changed / total if total else 0.0


def assert_matches_baseline(page, name: str, browser_name: str,
                            tolerance_ratio: float = 0.0,
                            mask: list[str] | None = None) -> None:
    """Compare the current page against its stored baseline.

    mask is a list of selectors covering regions whose content legitimately
    changes, such as a panel showing today's date. Playwright paints a solid
    block over each masked element in both the baseline and the actual image,
    so everything around it is still compared.

    Masking is the right tool here rather than the two alternatives. Cropping to
    a smaller region would lose coverage of the header, footer and overall
    layout, which is most of what the test is for. Raising the tolerance until
    the changing content fits underneath it would hide real changes of the same
    size somewhere else on the page.

    Set NORTHLINE_UPDATE_BASELINES=1 to accept the current appearance as the
    new baseline, after reviewing why it changed.
    """
    baseline_dir = BASELINE_DIR / platform_key() / browser_name
    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline = baseline_dir / name

    actual_dir = DIFF_DIR / platform_key() / browser_name
    actual_dir.mkdir(parents=True, exist_ok=True)
    actual = actual_dir / f"actual-{name}"

    masks = [page.locator(selector) for selector in (mask or [])]
    page.screenshot(path=str(actual), full_page=True, mask=masks)

    if _update_requested() or not baseline.exists():
        with Image.open(actual) as img:
            img.save(baseline)
        if _update_requested():
            return
        raise AssertionError(
            f"No baseline existed for {platform_key()}/{browser_name}/{name}, so one was created from "
            f"this run: {baseline.relative_to(REPO_ROOT)}\n"
            "Review the image, commit it, and re-run. The first run fails on purpose: "
            "accepting a screenshot as correct without anyone looking at it would mean "
            "the baseline can never be wrong."
        )

    diff_out = actual_dir / f"diff-{name}"
    ratio = changed_pixel_ratio(baseline, actual, diff_out)

    if ratio > tolerance_ratio:
        raise AssertionError(
            f"{platform_key()}/{browser_name}/{name} differs from its baseline: "
            f"{ratio:.4%} of pixels changed, tolerance {tolerance_ratio:.4%}.\n"
            f"  baseline: {baseline.relative_to(REPO_ROOT)}\n"
            f"  actual:   {actual.relative_to(REPO_ROOT)}\n"
            f"  diff:     {diff_out.relative_to(REPO_ROOT)}\n"
            "If the change is intended, re-run with NORTHLINE_UPDATE_BASELINES=1 "
            "and commit the updated baseline."
        )
