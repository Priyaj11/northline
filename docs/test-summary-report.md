# Test summary report

    release      R1.0
    environment  local
    generated    2026-08-31T06:02:23.702566+00:00

```
    RELEASE DECISION: NO-GO
```

Every figure below is counted from a file produced by a run that happened.
Where a number cannot be derived from the evidence, this report says so
rather than estimating it.

## Execution

| Measure | Value |
| --- | --- |
| Test cases recorded in the run | 114 |
| Executed | 94 |
| Not passed | 0 |
| Skipped or expected failure | 20 |
| Pass rate | 100.0 percent |

Expected failures are counted as skipped, which is how pytest records them
in JUnit XML. Each one is a known defect whose test is marked so the suite
stays green for NEW regressions. They are not hidden: every one appears in
the defect register below, and the release gate reads that register rather
than these results.

## By suite

| Suite | Recorded | Executed | Not passed | Expected failures | Pass rate | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Smoke | 5 | 5 | 0 | 0 | 100.0% | `reports/junit-smoke.xml` |
| API | 31 | 26 | 0 | 5 | 100.0% | `reports/junit-api.xml` |
| User interface | 14 | 14 | 0 | 0 | 100.0% | `reports/junit-ui.xml` |
| Database and ledger | 16 | 15 | 0 | 1 | 100.0% | `reports/junit-database.xml` |
| Reconciliation | 18 | 18 | 0 | 0 | 100.0% | `reports/junit-reconciliation.xml` |
| Accessibility | 19 | 10 | 0 | 9 | 100.0% | `reports/junit-accessibility.xml` |
| Security-adjacent | 11 | 6 | 0 | 5 | 100.0% | `reports/junit-security.xml` |

## Defects

    total                        7
    open                         7
    open and release blocking    5

### By severity

| Severity | Count |
| --- | --- |
| Critical | 3 |
| High | 2 |
| Medium | 2 |
| Low | 0 |

### By detection stage

| Phase | Count |
| --- | --- |
| Phase 3 | 2 |
| Phase 5 | 4 |
| Phase 7 | 1 |

### By detection method

| Method | Count |
| --- | --- |
| designed test case | 6 |
| exploratory | 1 |

Detection stage answers a question a release board asks: was this found
early or late. Detection method answers another: did the test design find
it, or did somebody find it by looking around. Both matter, and a report
that credits everything to the test design overstates it.

## Requirement coverage

    requirements                 41
    test cases                   72
    requirements with a test     41
    coverage                     100.0 percent
    requirements with a defect   10

Coverage here means every requirement has at least one test case. It does
NOT mean every requirement is fully verified: a requirement with one
shallow case counts the same as one with fifteen thorough ones. Reported
this way because that is what the number actually measures.

### Automation linkage, stated honestly

    test cases in the registers          72
    naming a specific automated test     5

Only those cases carry a verifiable link between a test case identifier
and the function that runs it. The rest are automated at suite level: the
suite covering that area runs, but nothing in the data proves which
function corresponds to which case identifier.

The result column of the traceability matrix is populated only for cases
with that explicit link. Matching the others by name would be guessing,
and a traceability matrix built on guesses is worse than one with an
honest gap, because nobody can tell which rows are trustworthy.

## Settlement reconciliation

    ledger records      54
    settlement records  54
    matched             54
    breaks              0
    status              PASS

## Performance

| Threads requested | Peak concurrency | Samples | Errors | p95 | Status |
| --- | --- | --- | --- | --- | --- |
| 10 | 3 | 1200 | 0 | 13.0 ms | PASS |
| 25 | 10 | 3000 | 0 | 27.0 ms | PASS |
| 50 | 40 | 6000 | 0 | 191.0 ms | PASS |

Run locally, not in continuous integration. A shared runner's timing is
not comparable between runs. See docs/performance-notes.md, which records
the first run being green and invalid.

## Release decision

    decision   NO-GO
    gates      8 of 10 passed

Blocking:

    GATE-CRITICAL-DEFECT

Recorded concerns:

    GATE-ACCESSIBILITY

Produced mechanically by scripts/certify.py from the thresholds in
quality-gates.yaml. The full breakdown, with the evidence file behind
every figure, is in docs/release-certification.md.

## What this report does not contain

    time to fix, reopen rate, fix effectiveness
        No defect has been fixed, so there is no fix history to measure.

    defect density per thousand lines
        The application under test is third-party code whose size is not
        measured here, and dividing by a number nobody counted is not a
        metric.

    manual accessibility results
        docs/accessibility-manual-checklist.md has a blank result column
        because those checks have not been performed. A checklist filled in
        without performing the checks looks like evidence and is not.

    User Acceptance Testing results
        Scenarios are designed and recorded as designed, not executed. There
        is no business user to execute them, and claiming otherwise would be
        fiction.
