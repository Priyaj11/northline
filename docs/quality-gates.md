# Quality Gates

The thresholds live in quality-gates.yaml at the repository root. That file is
the source of truth; the certification engine in Phase 7 reads it directly. This
document explains what the gates mean and why they are set where they are.

## How a decision is reached

  GO              Every gate passed.
  CONDITIONAL GO  No NO-GO gate failed, and at least one CONDITIONAL-GO gate
                  failed. The release may ship with the breach recorded and the
                  risk explicitly accepted.
  NO-GO           At least one gate whose failure mode is NO-GO failed.

## The gates that stop a release

  GATE-ENV               Environment readiness must pass
  GATE-SMOKE             Zero smoke failures
  GATE-CRITICAL-DEFECT   Zero open Critical or High defects
  GATE-RECON             Zero unexplained reconciliation breaks
  GATE-API-PASS          100 percent API pass rate

These share a property: each one, if breached, means either the results cannot
be trusted or money and customer data are at risk. Neither is negotiable.

## The gates that allow a conditional release

  GATE-UI-PASS        95 percent UI pass rate
  GATE-ACCESSIBILITY  Zero critical or serious violations
  GATE-PERF-P95       95th percentile under 2000 milliseconds
  GATE-PERF-ERROR     Error rate under 1 percent
  GATE-COVERAGE       Requirement coverage at or above 90 percent

These can be breached with an accepted, recorded risk and a remediation
commitment.

## Two threshold choices worth defending

Why the UI gate is 95 and not 100. Browser tests carry real flakiness from
timing and rendering. A team that sees red builds it cannot explain learns to
ignore red builds, and that is far more dangerous than an honest tolerance.
Every failure below the line is still triaged. The number is a tolerance for
flakiness, not permission to leave defects unfixed.

Why the 95th percentile and not the average. An average hides the slow tail.
If five percent of customers wait thirty seconds, the average still looks
healthy and those customers still leave.

## Honesty about coverage

Requirement coverage means every requirement has at least one test that ran. It
does not mean the requirement is fully verified. A requirement with one shallow
test counts the same as one with fifteen thorough tests. The number is a
completeness check on the traceability matrix, not a quality measure, and it is
reported that way.

## Where these numbers would really come from

In a bank, gate thresholds come from service level agreements, regulatory
obligations and risk appetite, decided by people other than the QA engineer.
The numbers here are a single engineer's judgement for a demonstration
application on one laptop. They are configuration rather than code precisely so
that changing them is a visible decision.

## Two kinds of generated document, two different rules

The determinism rule above applies to generated VIEWS, not to generated RECORDS.

    docs/requirements.md            a view of requirements.yaml
    docs/defect-report.md           a view of defects/register.yaml
    docs/requirements-traceability-matrix.md
    test-cases/*.md

Those are regenerated from registers, so the same inputs must produce the same
bytes, and the drift check compares them against the committed copy. A timestamp
in one makes that check impossible to satisfy.

    docs/release-certification.md   a decision made at a moment
    docs/accessibility-report.md    a scan of a running application

Those are records. They describe what was true when they were produced, they
carry a date on purpose, and regenerating one legitimately produces a different
document. They are committed as point-in-time artefacts and are NOT part of the
drift check.

The distinction is worth stating because the two look alike in a directory
listing. A certificate without a date is not a certificate, and a view that
changes every time it is regenerated cannot be checked for drift.
