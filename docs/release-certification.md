# Release certification

    release      R1.0
    environment  local
    evaluated    2026-08-31T05:16:17.024576+00:00

```
    DECISION: NO-GO
```

8 of 10 gates passed.

This decision is produced mechanically by scripts/certify.py from the
thresholds in quality-gates.yaml and the evidence files listed below. It is
not a judgement call, and every figure traces to a file a run produced.

## Gates

| Gate | Outcome | Observed | Threshold | On failure | Evidence |
| --- | --- | --- | --- | --- | --- |
| GATE-ENV Environment readiness | **PASS** | passed | must_pass | NO-GO | `reports/environment.json` |
| GATE-SMOKE Smoke suite | **PASS** | 0 | 0 | NO-GO | `reports/junit-smoke.xml` |
| GATE-CRITICAL-DEFECT Critical and high defects | **FAIL** | 5 | 0 | NO-GO | `reports/defects.json` |
| GATE-RECON Settlement reconciliation | **PASS** | 0 | 0 | NO-GO | `reports/reconciliation-report.json` |
| GATE-API-PASS API suite pass rate | **PASS** | 100.0 | 100 | NO-GO | `reports/junit-api.xml` |
| GATE-UI-PASS UI regression pass rate | **PASS** | 100.0 | 95 | CONDITIONAL-GO | `reports/junit-ui.xml` |
| GATE-ACCESSIBILITY Accessibility violations | **FAIL** | 26 | 0 | CONDITIONAL-GO | `reports/accessibility-scan.json` |
| GATE-PERF-P95 Performance 95th percentile | **PASS** | 191.0 | 2000 | CONDITIONAL-GO | `reports/performance-report.json (worst profile)` |
| GATE-PERF-ERROR Performance error rate | **PASS** | 0.0 | 1 | CONDITIONAL-GO | `reports/performance-report.json (worst profile)` |
| GATE-COVERAGE Requirement coverage | **PASS** | 100.0 | 90 | CONDITIONAL-GO | `reports/traceability.json` |

## Why this release is blocked

### GATE-CRITICAL-DEFECT Critical and high defects

    rule       No open defect of severity Critical or High
    observed   5
    threshold  0
    evidence   reports/defects.json

5.0 against a maximum of 0.0 open defects allowed

## Recorded concerns

These do not block the release. Shipping with any of them requires the
breach recorded, the risk accepted by name, and a remediation date.

| Gate | Observed | Threshold | Detail |
| --- | --- | --- | --- |
| GATE-ACCESSIBILITY Accessibility violations | 26 | 0 | 26.0 against a maximum of 0.0 critical or serious violations allowed |

## How to read the decision

    GO              every gate passed
    CONDITIONAL GO  no blocking gate failed, but something else did
    NO-GO           at least one gate whose failure mode is NO-GO did not pass

Every gate is evaluated even after one has already forced a NO-GO. A report
that stopped at the first blocking problem would name one thing and hide the
rest, and the point of this document is to tell a team everything they need
to fix.
