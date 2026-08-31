"""Produce the release certification decision.

Reads quality-gates.yaml and the evidence on disk, evaluates every gate, and
writes:

    docs/release-certification.md    the readable decision
    reports/certification.json       the machine-readable one

Exit code 0 for GO, 0 for CONDITIONAL GO, 1 for NO-GO. A conditional release is
a release, so it does not fail the pipeline; it requires the breach recorded and
the risk accepted, which is a human decision rather than an exit code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from certification.evaluator import certify  # noqa: E402
from certification.evidence import collect  # noqa: E402
from certification.models import Certification, Decision, Outcome  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("certify")

REPO_ROOT = Path(__file__).resolve().parent.parent
GATES = REPO_ROOT / "quality-gates.yaml"
OUTPUT = REPO_ROOT / "docs" / "release-certification.md"

SYMBOL = {Outcome.PASS: "PASS", Outcome.FAIL: "FAIL", Outcome.NO_EVIDENCE: "NO EVIDENCE"}


def render(result: Certification, notes: list[str]) -> str:
    lines = [
        "# Release certification",
        "",
        f"    release      {result.release}",
        f"    environment  {result.environment}",
        f"    evaluated    {result.evaluated_at.isoformat() if result.evaluated_at else 'unknown'}",
        "",
        "```",
        f"    DECISION: {result.decision.value}",
        "```",
        "",
        f"{len(result.passed)} of {len(result.results)} gates passed.",
        "",
        "This decision is produced mechanically by scripts/certify.py from the",
        "thresholds in quality-gates.yaml and the evidence files listed below. It is",
        "not a judgement call, and every figure traces to a file a run produced.",
        "",
        "## Gates",
        "",
        "| Gate | Outcome | Observed | Threshold | On failure | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in result.results:
        lines.append(
            f"| {r.gate_id} {r.name} | **{SYMBOL[r.outcome]}** | {r.observed} | "
            f"{r.threshold} | {r.on_failure} | `{r.evidence_source}` |"
        )
    lines.append("")

    if result.blocking:
        lines += ["## Why this release is blocked", ""]
        for r in result.blocking:
            lines += [f"### {r.gate_id} {r.name}", "",
                      f"    rule       {r.rule}",
                      f"    observed   {r.observed}",
                      f"    threshold  {r.threshold}",
                      f"    evidence   {r.evidence_source}", ""]
            if r.detail:
                lines += [" ".join(r.detail.split()), ""]

    if result.concerns:
        lines += ["## Recorded concerns", "",
                  "These do not block the release. Shipping with any of them requires the",
                  "breach recorded, the risk accepted by name, and a remediation date.",
                  "", "| Gate | Observed | Threshold | Detail |", "| --- | --- | --- | --- |"]
        for r in result.concerns:
            lines.append(f"| {r.gate_id} {r.name} | {r.observed} | {r.threshold} | "
                         f"{' '.join(r.detail.split())} |")
        lines.append("")

    if notes:
        lines += ["## Evidence that could not be found", ""]
        lines += [f"    {n}" for n in notes]
        lines += ["",
                  "A missing report does NOT satisfy its gate. It is recorded as 'no",
                  "evidence', which does not pass, because a release must not be certified",
                  "on the strength of checks that never ran. Deleting a report file must",
                  "never be a way to get a release through.",
                  ""]

    lines += [
        "## How to read the decision",
        "",
        "    GO              every gate passed",
        "    CONDITIONAL GO  no blocking gate failed, but something else did",
        "    NO-GO           at least one gate whose failure mode is NO-GO did not pass",
        "",
        "Every gate is evaluated even after one has already forced a NO-GO. A report",
        "that stopped at the first blocking problem would name one thing and hide the",
        "rest, and the point of this document is to tell a team everything they need",
        "to fix.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    settings = get_settings()
    gates = yaml.safe_load(GATES.read_text())["gates"]

    evidence, notes = collect()
    log.info("Collected evidence for %d of %d gates", len(evidence), len(gates))
    for note in notes:
        log.warning("%s", note)

    result = certify(gates, evidence, settings.release, settings.environment)

    OUTPUT.write_text(render(result, notes))
    payload = result.as_dict()
    payload["evidence_not_found"] = notes
    (settings.reports_dir / "certification.json").write_text(json.dumps(payload, indent=2))

    print()
    print(render(result, notes))

    log.info("DECISION: %s (%d of %d gates passed)",
             result.decision.value, len(result.passed), len(result.results))
    for r in result.blocking:
        log.error("BLOCKING  %s %s: observed %s against %s",
                  r.gate_id, r.name, r.observed, r.threshold)
    for r in result.concerns:
        log.warning("CONCERN   %s %s: observed %s against %s",
                    r.gate_id, r.name, r.observed, r.threshold)

    return 1 if result.decision is Decision.NO_GO else 0


if __name__ == "__main__":
    sys.exit(main())
