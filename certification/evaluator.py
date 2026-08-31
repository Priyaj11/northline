"""The release certification engine.

Takes gate definitions and collected evidence, applies each gate, and returns a
decision. A pure function over two dictionaries: no file reading, no network, no
database, so the decision logic can be tested exhaustively without an
environment.

That separation matters more here than anywhere else in the project. This is
the component that says whether a release ships. If it can only be tested by
running the entire suite first, it will not be tested thoroughly, and a release
gate nobody has tested is decoration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from certification.models import Certification, Decision, GateResult, Outcome


def _numeric(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_gate(gate: dict, evidence: dict) -> GateResult:
    """Apply one gate to the evidence collected for it.

    evidence maps a gate identifier to a dict with at least:
        observed  the measured value, or None when nothing was collected
        source    where it came from, for the report
    """
    gate_id = gate["id"]
    found = evidence.get(gate_id) or {}
    observed = found.get("observed")
    source = found.get("source", "not collected")
    threshold = gate["threshold"]

    common = {
        "gate_id": gate_id,
        "name": gate["name"],
        "rule": " ".join(str(gate["rule"]).split()),
        "threshold": str(threshold),
        "on_failure": gate["on_failure"],
        "evidence_source": source,
    }

    if observed is None:
        return GateResult(
            outcome=Outcome.NO_EVIDENCE,
            observed="none",
            detail=(
                "No evidence was collected for this gate. Treated as not met "
                "rather than passed: a release must not be certified on the "
                "strength of a check that never ran."
            ),
            **common,
        )

    if threshold == "must_pass":
        ok = bool(observed)
        return GateResult(
            outcome=Outcome.PASS if ok else Outcome.FAIL,
            observed="passed" if ok else "failed",
            detail="" if ok else "The check did not pass.",
            **common,
        )

    limit = _numeric(threshold)
    value = _numeric(observed)
    if limit is None or value is None:
        return GateResult(
            outcome=Outcome.NO_EVIDENCE,
            observed=str(observed),
            detail=f"Could not compare {observed!r} against threshold {threshold!r}.",
            **common,
        )

    # Which direction the comparison runs is stated in quality-gates.yaml, not
    # inferred here.
    #
    #   maximum   the observed value must not exceed the threshold
    #             (failed tests, reconciliation breaks, milliseconds, error rate)
    #   minimum   the observed value must meet or exceed it
    #             (pass rates, requirement coverage)
    #
    # An earlier version guessed the direction from the gate's name: percentages
    # were minimums unless the name contained "rate". "UI regression pass rate"
    # contains "rate", so a 100 percent pass rate was compared as a maximum and
    # failed. The unit test caught it immediately.
    #
    # The lesson is not that the heuristic needed another exception. It is that
    # the direction of a comparison is a property of the gate, and inferring it
    # from how somebody worded a title is how a release decision comes out
    # backwards.
    comparison = gate.get("comparison")
    if comparison not in ("minimum", "maximum"):
        return GateResult(
            outcome=Outcome.NO_EVIDENCE,
            observed=str(observed),
            detail=(
                f"Gate {gate_id} has no valid 'comparison' field. It must be "
                "'minimum' or 'maximum'. Refusing to guess."
            ),
            **common,
        )

    if comparison == "minimum":
        ok = value >= limit
        detail = f"{value} against a minimum of {limit}"
    else:
        ok = value <= limit
        detail = f"{value} against a maximum of {limit}"

    return GateResult(
        outcome=Outcome.PASS if ok else Outcome.FAIL,
        observed=str(observed),
        detail=detail + (f" {gate['unit']}" if gate.get("unit") else ""),
        **common,
    )


def certify(gates: list[dict], evidence: dict, release: str, environment: str) -> Certification:
    """Evaluate every gate and reach a decision.

    The decision rules come from quality-gates.yaml:

        NO-GO           any gate whose on_failure is NO-GO did not pass
        CONDITIONAL GO  no NO-GO gate failed, but something else did
        GO              everything passed

    Every gate is evaluated even after one has already forced a NO-GO. Stopping
    at the first blocking failure would produce a report that names one problem
    and hides the rest, and the point of the report is to tell a team everything
    they need to fix.
    """
    results = [evaluate_gate(gate, evidence) for gate in gates]

    if any(r.blocks_release for r in results):
        decision = Decision.NO_GO
    elif any(r.is_concern for r in results):
        decision = Decision.CONDITIONAL_GO
    else:
        decision = Decision.GO

    return Certification(
        release=release,
        environment=environment,
        decision=decision,
        results=results,
        evaluated_at=datetime.now(tz=timezone.utc),
    )
