"""Tests for the release certification engine.

Covers the decision logic that says whether a release ships. It is the
component with the most authority in the project and the least visible failure
mode: a gate that quietly passes when it should fail produces a confident GO on
a broken release, and nothing downstream would catch it.

So every gate shape is tested in both directions, and the three decision
outcomes are tested from constructed evidence rather than from a real run.
"""

from __future__ import annotations

import pytest

from certification.evaluator import certify, evaluate_gate
from certification.models import Decision, Outcome

pytestmark = pytest.mark.certification


def gate(gate_id="G", threshold=0, unit="failed tests allowed",
         on_failure="NO-GO", name="Test gate", rule="a rule",
         comparison="maximum"):
    return {"id": gate_id, "name": name, "rule": rule, "threshold": threshold,
            "unit": unit, "on_failure": on_failure, "comparison": comparison}


def evidence(value, source="test"):
    return {"G": {"observed": value, "source": source}}


# --- gate shapes ------------------------------------------------------------

def test_a_must_pass_gate_passes_when_the_check_passed():
    assert evaluate_gate(gate(threshold="must_pass", unit=""),
                         evidence(True)).outcome is Outcome.PASS


def test_a_must_pass_gate_fails_when_the_check_failed():
    result = evaluate_gate(gate(threshold="must_pass", unit=""), evidence(False))
    assert result.outcome is Outcome.FAIL
    assert result.blocks_release


def test_a_maximum_gate_passes_at_the_threshold():
    """Boundary value. A threshold of zero failures allows exactly zero."""
    assert evaluate_gate(gate(threshold=0), evidence(0)).outcome is Outcome.PASS


def test_a_maximum_gate_fails_one_past_the_threshold():
    assert evaluate_gate(gate(threshold=0), evidence(1)).outcome is Outcome.FAIL


def test_a_millisecond_gate_compares_as_a_maximum():
    p95 = gate(threshold=2000, unit="milliseconds", name="Performance 95th percentile")
    assert evaluate_gate(p95, evidence(191)).outcome is Outcome.PASS
    assert evaluate_gate(p95, evidence(2500)).outcome is Outcome.FAIL


def test_a_pass_rate_gate_compares_as_a_minimum():
    """A pass rate must MEET its threshold, not stay under it.

    This is the comparison most likely to be written backwards, and an earlier
    version of the engine got it wrong: it inferred direction from the gate's
    name, and "UI regression pass rate" contains the word rate, so a 100 percent
    pass rate was compared as a maximum and failed.
    """
    rate = gate(threshold=95, unit="percent", name="UI regression pass rate",
                comparison="minimum")
    assert evaluate_gate(rate, evidence(100)).outcome is Outcome.PASS
    assert evaluate_gate(rate, evidence(95)).outcome is Outcome.PASS
    assert evaluate_gate(rate, evidence(94.9)).outcome is Outcome.FAIL
    assert evaluate_gate(rate, evidence(0)).outcome is Outcome.FAIL


def test_an_error_rate_gate_compares_as_a_maximum():
    """An error rate must stay UNDER its threshold, unlike a pass rate. Both are
    percentages, which is exactly why the direction is configured rather than
    inferred."""
    errors = gate(threshold=1, unit="percent", name="Performance error rate")
    assert evaluate_gate(errors, evidence(0)).outcome is Outcome.PASS
    assert evaluate_gate(errors, evidence(0.9)).outcome is Outcome.PASS
    assert evaluate_gate(errors, evidence(1.7)).outcome is Outcome.FAIL


def test_a_coverage_gate_compares_as_a_minimum():
    coverage = gate(threshold=90, unit="percent", name="Requirement coverage",
                    comparison="minimum")
    assert evaluate_gate(coverage, evidence(100)).outcome is Outcome.PASS
    assert evaluate_gate(coverage, evidence(89)).outcome is Outcome.FAIL


def test_a_gate_with_no_comparison_direction_is_refused():
    """The engine will not guess which way a comparison runs.

    Refusing is safer than guessing: a misconfigured gate becomes visible rather
    than producing a confident wrong answer.
    """
    broken = {"id": "G", "name": "n", "rule": "r", "threshold": 95,
              "unit": "percent", "on_failure": "NO-GO"}
    result = evaluate_gate(broken, evidence(100))
    assert result.outcome is Outcome.NO_EVIDENCE
    assert "Refusing to guess" in result.detail


# --- missing evidence -------------------------------------------------------

def test_missing_evidence_is_not_a_pass():
    """The most dangerous failure mode this engine could have.

    A suite that never ran leaves no report. If that silently satisfied its
    gate, deleting a report file would be enough to certify a release.
    """
    result = evaluate_gate(gate(), {})
    assert result.outcome is Outcome.NO_EVIDENCE
    assert result.blocks_release, "A blocking gate with no evidence must still block"


def test_missing_evidence_on_a_non_blocking_gate_is_a_concern_not_a_block():
    result = evaluate_gate(gate(on_failure="CONDITIONAL-GO"), {})
    assert result.outcome is Outcome.NO_EVIDENCE
    assert not result.blocks_release
    assert result.is_concern


def test_evidence_that_cannot_be_compared_is_not_a_pass():
    assert evaluate_gate(gate(threshold=0),
                         evidence("not a number")).outcome is Outcome.NO_EVIDENCE


# --- the three decisions ----------------------------------------------------

def three_gates():
    return [
        gate("BLOCKING", threshold=0, on_failure="NO-GO"),
        gate("SOFT", threshold=0, on_failure="CONDITIONAL-GO"),
        gate("ALSO-SOFT", threshold=0, on_failure="CONDITIONAL-GO"),
    ]


def all_evidence(blocking=0, soft=0, also_soft=0):
    return {
        "BLOCKING": {"observed": blocking, "source": "test"},
        "SOFT": {"observed": soft, "source": "test"},
        "ALSO-SOFT": {"observed": also_soft, "source": "test"},
    }


def test_everything_passing_gives_go():
    result = certify(three_gates(), all_evidence(), "R1.0", "test")
    assert result.decision is Decision.GO
    assert len(result.passed) == 3


def test_a_soft_gate_failing_gives_conditional_go():
    result = certify(three_gates(), all_evidence(soft=5), "R1.0", "test")
    assert result.decision is Decision.CONDITIONAL_GO
    assert [r.gate_id for r in result.concerns] == ["SOFT"]
    assert not result.blocking


def test_a_blocking_gate_failing_gives_no_go():
    result = certify(three_gates(), all_evidence(blocking=1), "R1.0", "test")
    assert result.decision is Decision.NO_GO
    assert [r.gate_id for r in result.blocking] == ["BLOCKING"]


def test_a_blocking_failure_outranks_soft_failures():
    result = certify(three_gates(), all_evidence(blocking=1, soft=9, also_soft=9),
                     "R1.0", "test")
    assert result.decision is Decision.NO_GO


def test_every_gate_is_evaluated_even_after_a_blocking_failure():
    """A report that stops at the first blocking problem hides the rest, and the
    point of the report is to tell a team everything they need to fix."""
    result = certify(three_gates(), all_evidence(blocking=1, soft=5, also_soft=5),
                     "R1.0", "test")
    assert len(result.results) == 3
    assert len(result.concerns) == 2
    assert len(result.blocking) == 1


def test_no_evidence_at_all_gives_no_go():
    """The empty case. A release with no results is not a release that passed."""
    result = certify(three_gates(), {}, "R1.0", "test")
    assert result.decision is Decision.NO_GO
    assert all(r.outcome is Outcome.NO_EVIDENCE for r in result.results)


def test_the_decision_serialises_for_the_summary_report():
    payload = certify(three_gates(), all_evidence(blocking=1), "R1.0", "local").as_dict()
    assert payload["decision"] == "NO-GO"
    assert payload["gates_total"] == 3
    assert payload["gates_blocking"] == ["BLOCKING"]
    assert len(payload["results"]) == 3
