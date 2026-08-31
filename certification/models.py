"""Data structures for the release certification decision.

A gate is a rule with a threshold and a consequence. A gate result is that rule
applied to one piece of evidence. The decision is what all the gate results add
up to.

Three outcomes, defined in quality-gates.yaml:

    GO              every gate passed
    CONDITIONAL GO  no blocking gate failed, and at least one non-blocking one did
    NO-GO           at least one gate whose failure mode is NO-GO failed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    #: The gate could not be evaluated because its evidence was missing. This is
    #: deliberately NOT a pass. A release must not be certified on the strength
    #: of checks that never ran, and a missing report is indistinguishable from
    #: a suite that was quietly skipped.
    NO_EVIDENCE = "no evidence"


class Decision(str, Enum):
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL GO"
    NO_GO = "NO-GO"


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    name: str
    rule: str
    outcome: Outcome
    threshold: str
    observed: str
    on_failure: str
    evidence_source: str
    detail: str = ""

    @property
    def blocks_release(self) -> bool:
        """A failed or unevaluated gate blocks only if its failure mode says so."""
        return self.outcome is not Outcome.PASS and self.on_failure == "NO-GO"

    @property
    def is_concern(self) -> bool:
        return self.outcome is not Outcome.PASS and self.on_failure != "NO-GO"


@dataclass
class Certification:
    release: str
    environment: str
    decision: Decision
    results: list[GateResult] = field(default_factory=list)
    evaluated_at: datetime | None = None

    @property
    def blocking(self) -> list[GateResult]:
        return [r for r in self.results if r.blocks_release]

    @property
    def concerns(self) -> list[GateResult]:
        return [r for r in self.results if r.is_concern]

    @property
    def passed(self) -> list[GateResult]:
        return [r for r in self.results if r.outcome is Outcome.PASS]

    def as_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "release": self.release,
            "environment": self.environment,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "gates_total": len(self.results),
            "gates_passed": len(self.passed),
            "gates_blocking": [r.gate_id for r in self.blocking],
            "gates_of_concern": [r.gate_id for r in self.concerns],
            "results": [
                {
                    "gate_id": r.gate_id,
                    "name": r.name,
                    "rule": r.rule,
                    "outcome": r.outcome.value,
                    "threshold": r.threshold,
                    "observed": r.observed,
                    "on_failure": r.on_failure,
                    "evidence_source": r.evidence_source,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }
