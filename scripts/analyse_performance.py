"""Analyse JMeter results and check them against the configured thresholds.

Reads every reports/performance/profile-<users>.jtl file, computes response
time percentiles and error rates per request and per profile, compares them
against GATE-PERF-P95 and GATE-PERF-ERROR in quality-gates.yaml, and writes:

    reports/performance-report.md      the readable report
    reports/performance-report.json    read by the Phase 7 certification engine

Exit code 0 when every profile meets the thresholds, 1 when any does not.

ON PERCENTILES

The 95th percentile is the value below which 95 percent of responses fall. It
is used instead of the average because an average hides the slow tail: if one
request in twenty takes thirty seconds, the average still looks healthy and
those customers still leave.

The nearest-rank method is used, which takes the value at position
ceil(0.95 * n) in the sorted list. Different tools interpolate differently, so
the method is stated rather than left implicit. Comparing a percentile from one
tool against a threshold set by another without knowing both methods is a
common way to be quietly wrong.

NO NUMBER IN THIS REPORT IS ESTIMATED. Every figure comes from a JMeter result
file produced by a run that actually happened.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("analyse_performance")

REPO_ROOT = Path(__file__).resolve().parent.parent
GATES = REPO_ROOT / "quality-gates.yaml"
RESULTS_DIR = REPO_ROOT / "reports" / "performance"
PROFILE_PATTERN = re.compile(r"profile-(\d+)\.jtl$")


def percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile. Stated explicitly, see the module docstring."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def read_jtl(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarise_samples(samples: list[dict]) -> dict:
    elapsed = [float(s["elapsed"]) for s in samples]
    failures = [s for s in samples if s.get("success", "").strip().lower() != "true"]

    timestamps = [int(s["timeStamp"]) for s in samples]
    span_seconds = (max(timestamps) - min(timestamps)) / 1000 if len(timestamps) > 1 else 0.0

    # allThreads is JMeter's record of how many threads were active when each
    # sample was taken. It is the only trustworthy answer to "what concurrency
    # did this run ACTUALLY achieve", which is not the same as the number of
    # threads requested.
    concurrency = [int(s["allThreads"]) for s in samples if s.get("allThreads", "").strip().isdigit()]

    return {
        "samples": len(samples),
        "peak_concurrency": max(concurrency) if concurrency else None,
        "mean_concurrency": round(mean(concurrency), 1) if concurrency else None,
        "errors": len(failures),
        "error_rate_percent": round(100 * len(failures) / len(samples), 3) if samples else 0.0,
        "min_ms": round(min(elapsed), 1) if elapsed else 0.0,
        "mean_ms": round(mean(elapsed), 1) if elapsed else 0.0,
        "p50_ms": round(percentile(elapsed, 0.50), 1),
        "p90_ms": round(percentile(elapsed, 0.90), 1),
        "p95_ms": round(percentile(elapsed, 0.95), 1),
        "p99_ms": round(percentile(elapsed, 0.99), 1),
        "max_ms": round(max(elapsed), 1) if elapsed else 0.0,
        "throughput_per_second": round(len(samples) / span_seconds, 2) if span_seconds else None,
        "failure_messages": sorted({s.get("failureMessage", "") for s in failures if s.get("failureMessage")}),
    }


def load_thresholds() -> tuple[float, float]:
    gates = yaml.safe_load(GATES.read_text())["gates"]
    by_id = {g["id"]: g for g in gates}
    return float(by_id["GATE-PERF-P95"]["threshold"]), float(by_id["GATE-PERF-ERROR"]["threshold"])


def main() -> int:
    settings = get_settings()
    p95_limit, error_limit = load_thresholds()
    log.info("Thresholds from quality-gates.yaml: p95 < %s ms, error rate < %s percent",
             p95_limit, error_limit)

    files = sorted(RESULTS_DIR.glob("profile-*.jtl"),
                   key=lambda p: int(PROFILE_PATTERN.search(p.name).group(1)))
    if not files:
        log.error("No result files found in %s. Run the profiles first.", RESULTS_DIR)
        return 1

    profiles = []
    overall_pass = True

    for path in files:
        users = int(PROFILE_PATTERN.search(path.name).group(1))
        samples = read_jtl(path)
        if not samples:
            log.error("%s contains no samples", path.name)
            overall_pass = False
            continue

        by_label: dict[str, list[dict]] = defaultdict(list)
        for sample in samples:
            by_label[sample["label"]].append(sample)

        overall = summarise_samples(samples)
        requests = {label: summarise_samples(rows) for label, rows in sorted(by_label.items())}

        p95_ok = overall["p95_ms"] < p95_limit
        error_ok = overall["error_rate_percent"] < error_limit
        profile_pass = p95_ok and error_ok
        overall_pass = overall_pass and profile_pass

        achieved = overall["peak_concurrency"]
        if achieved is not None and achieved < users:
            log.warning(
                "%2d users requested but peak concurrency observed was %d. "
                "The numbers describe the concurrency actually achieved.",
                users, achieved,
            )

        profiles.append({
            "users_requested": users,
            "peak_concurrency_observed": achieved,
            "users": users,
            "file": path.name,
            "overall": overall,
            "requests": requests,
            "p95_within_threshold": p95_ok,
            "error_rate_within_threshold": error_ok,
            "status": "pass" if profile_pass else "fail",
        })

        log.info("%2d users: %d samples, p95 %s ms, errors %s percent -> %s",
                 users, overall["samples"], overall["p95_ms"],
                 overall["error_rate_percent"], "pass" if profile_pass else "FAIL")

    report = {
        "status": "pass" if overall_pass else "fail",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "environment": settings.environment,
        "release": settings.release,
        "thresholds": {"p95_ms": p95_limit, "error_rate_percent": error_limit},
        "percentile_method": "nearest rank",
        "profiles": profiles,
    }

    json_path = settings.reports_dir / "performance-report.json"
    json_path.write_text(json.dumps(report, indent=2))

    md_path = settings.reports_dir / "performance-report.md"
    md_path.write_text(render(report))

    log.info("Wrote %s and %s", md_path.name, json_path.name)
    print()
    print(render(report))

    return 0 if overall_pass else 1


def render(report: dict) -> str:
    lines = [
        "# Performance report",
        "",
        f"Generated {report['generated_at']} for environment {report['environment']}, "
        f"release {report['release']}.",
        "Every figure below comes from a JMeter result file produced by a run that",
        "actually happened. Nothing is estimated.",
        "",
        f"    thresholds:        95th percentile < {report['thresholds']['p95_ms']} ms, "
        f"error rate < {report['thresholds']['error_rate_percent']} percent",
        f"    percentile method: {report['percentile_method']}",
        f"    overall status:    {report['status'].upper()}",
        "",
        "## Summary by load profile",
        "",
        "| Threads requested | Peak concurrency observed | Samples | Errors | Error rate "
        "| Throughput/s | p50 | p90 | p95 | p99 | Max | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for profile in report["profiles"]:
        o = profile["overall"]
        lines.append(
            f"| {profile['users_requested']} | {o['peak_concurrency'] if o['peak_concurrency'] is not None else '-'} "
            f"| {o['samples']} | {o['errors']} | "
            f"{o['error_rate_percent']}% "
            f"| {o['throughput_per_second'] if o['throughput_per_second'] is not None else '-'} "
            f"| {o['p50_ms']} | {o['p90_ms']} | {o['p95_ms']} | "
            f"{o['p99_ms']} | {o['max_ms']} | {profile['status'].upper()} |"
        )
    lines += [
        "",
        "All times in milliseconds.",
        "",
        "Peak concurrency observed comes from JMeter's allThreads field, which records",
        "how many threads were active when each sample was taken. It is reported next to",
        "the requested thread count because the two are NOT the same: threads that finish",
        "their work before the ramp completes are never concurrent with the ones that",
        "start after them. A run that reports its requested count rather than its achieved",
        "count is overstating the load it applied.",
        "",
    ]

    for profile in report["profiles"]:
        lines += [
            f"## {profile['users_requested']} threads requested, "
            f"{profile['overall']['peak_concurrency']} peak concurrency observed",
            "",
            f"Source: reports/performance/{profile['file']}",
            "",
            "| Request | Samples | Errors | Mean | p95 | p99 | Max | Throughput/s |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for label, stats in profile["requests"].items():
            lines.append(
                f"| {label} | {stats['samples']} | {stats['errors']} | {stats['mean_ms']} | "
                f"{stats['p95_ms']} | {stats['p99_ms']} | {stats['max_ms']} | "
                f"{stats['throughput_per_second'] if stats['throughput_per_second'] is not None else '-'} |"
            )
        lines.append("")
        failures = {m for stats in profile["requests"].values() for m in stats["failure_messages"]}
        if failures:
            lines += ["Failure messages observed:", ""]
            lines += [f"    {m}" for m in sorted(failures)]
            lines.append("")

    lines += [
        "## What these numbers do and do not mean",
        "",
        "They describe one laptop running the load generator, the application server",
        "and the database at the same time. They are NOT a capacity measurement, and",
        "no conclusion about how many customers the application could serve should be",
        "drawn from them.",
        "",
        "What they do demonstrate is a load profile applied, thresholds defined in",
        "configuration rather than in code, and results interpreted against them.",
        "",
        "The 95th percentile is used rather than the average because an average hides",
        "the slow tail. If one request in twenty takes thirty seconds, the average",
        "still looks healthy and those customers still leave.",
        "",
        "In a real bank these thresholds would come from service level agreements and",
        "regulatory obligations rather than from a QA engineer's judgement, and the",
        "load generator would not share a machine with the system under test.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
