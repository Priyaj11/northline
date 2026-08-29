# Release Certification Process

## The question this answers

Should this release ship, and what is the evidence.

## The flow

    Build identified and environment provisioned
              |
              v
    Environment readiness check          GATE-ENV
              |  fail -> NO-GO, stop
              v
    Smoke suite                          GATE-SMOKE
              |  fail -> NO-GO, stop
              v
    API suite                            GATE-API-PASS
    UI regression suite                  GATE-UI-PASS
    Database validation suite
              |
              v
    Settlement reconciliation            GATE-RECON
              |
              v
    Accessibility scan and manual pass   GATE-ACCESSIBILITY
    Security-adjacent suite
    Performance run                      GATE-PERF-P95, GATE-PERF-ERROR
              |
              v
    Defect triage, severity and priority GATE-CRITICAL-DEFECT
              |
              v
    Traceability matrix generated        GATE-COVERAGE
              |
              v
    Certification engine evaluates every gate
              |
              v
    GO  /  CONDITIONAL GO  /  NO-GO   plus the test summary report

## Why the order

The two cheapest and most decisive gates come first. There is no point spending
forty minutes on a full regression run to discover the environment was never
ready. This is fail-fast applied to a release process.

## What the decision is made from

Actual results only. Every number in the summary report traces to a test that
ran, a defect that was reproduced, or a reconciliation that was performed.
Nothing is estimated, and nothing is carried over from a previous run.

## What a CONDITIONAL GO obliges

A conditional release is not a passed release. It requires the breach recorded
with its evidence, the risk explicitly accepted and by whom, and a remediation
commitment with a target release. Without those three, it is a NO-GO.

## After the release

Any defect found in production is added to the regression suite before it is
closed. That is how a regression suite earns its size: every test in it exists
because something once went wrong.
