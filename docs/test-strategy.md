# Test Strategy

Release: R1.0
System Under Test: ParaBank
Environment: local

A test strategy says how testing will be approached and why. A test plan says
what will be done, by whom, and when. This is the strategy; the plan is in
docs/test-plan.md.

## Objectives

  1. Establish whether a ParaBank release is fit to ship, and produce the
     evidence behind that answer.
  2. Verify correctness at every layer, from the browser through the interface
     to the data, so that a screen saying "success" is never accepted as proof.
  3. Verify that money is conserved. Every movement debits one account and
     credits another by the same amount, and reconciles against settlement.
  4. Verify the application is usable by people relying on assistive technology.
  5. Produce a defensible GO, CONDITIONAL GO or NO-GO decision from real
     results rather than judgement.

## Scope

See docs/scope.md for the full in-scope and out-of-scope lists, and
docs/requirements.md for the 40 requirements this strategy covers.

## Testing levels

  Unit            Not applicable. ParaBank is a third-party application whose
                  source we neither own nor modify. Northline's own helper code
                  is covered by tests where it carries logic, notably the
                  reconciliation engine and the certification engine.

  Integration     Northline against ParaBank across its interfaces.

  System          End-to-end banking workflows through the browser interface.

  System          The signature level for this project. A workflow is followed
  Integration     from the browser, through the service layer, into the data,
  (SIT)           and out into the settlement extract, asserting at every stop.
                  Banking defects live between systems more often than inside
                  any one of them.

  Acceptance      Scenarios are designed and documented. They are NOT executed,
  (UAT)           because there is no business user to execute them and a demo
                  application has no business owner. Marked "designed, not
                  executed" in the traceability matrix. Claiming executed UAT
                  would be fiction.

## Testing types and what each one catches

  Smoke           Is this build worth testing at all. Runs in under a minute
                  and gates everything else.

  Functional      Does each feature behave as the requirement states.

  Regression      Did a change break something that previously worked. Grows
                  with every release and every fixed defect.

  User interface  Broken screens, broken navigation, broken client-side
                  validation, layout regressions. Playwright, Page Object
                  Model, across Chromium, Firefox and WebKit.

  API             Broken contracts, wrong status codes, wrong data types,
                  missing fields, poor error handling. Deterministic, fast, and
                  where most negative and boundary testing belongs.

  Database        The screen says the transfer succeeded. Did the data agree.
                  Catches the single most dangerous class of banking defect:
                  a confident interface over wrong data.

  Reconciliation  Money that does not add up between two systems. Settlement
                  extract compared against the certification data store,
                  detecting missing records, duplicates, amount mismatches and
                  account mismatches. Proven by deliberately injecting each of
                  those four break types.

  Accessibility   An interface unusable by people relying on screen readers or
                  keyboard navigation. Automated axe-core scanning against WCAG
                  2.1 level AA, plus a manual checklist for what automation
                  cannot see.

  Performance     Correct behaviour that is too slow to be usable. Apache JMeter
                  against login, account retrieval and transfer.

  Security-       Session handling, authorisation, and input validation. NOT
  adjacent        penetration testing. We test that the application enforces the
                  access rules it claims to enforce. We do not attempt to
                  exploit anything.

## Environment

One environment, named local, on a single development machine.

  ParaBank in Docker on port 8080
  PostgreSQL certification data store in Docker on host port 5433

A real bank would run Development, SIT, UAT and Production separately.
Northline simulates that by making the environment name a configuration value,
so every report and every certification decision records which environment
produced it.

## Test data

Summarised here, detailed in docs/test-data-strategy.md.

ParaBank exposes cleanDB and initializeDB service endpoints, which give a
deterministic reset. Tests that change money create their own customer through
registration rather than competing for the shared demo customer.

## Risks

  R1  ParaBank is a demonstration application with no published specification.
      Some requirements are assumptions. Mitigation: every requirement records
      its source as observed, derived or assumed, so a failure against an
      assumption is investigated before being reported as a defect.

  R2  Browser tests are inherently flaky. Mitigation: web-first assertions
      rather than fixed waits, retries in continuous integration only, trace
      and video captured on failure, and a UI pass-rate gate below 100 percent
      that is honest about this rather than pretending.

  R3  Test data drift. A transfer test run twice sees different balances.
      Mitigation: deterministic reset before suites that move money, and
      assertions on deltas rather than absolute balances where possible.

  R4  Single machine performance testing. Results describe this laptop, not
      production capacity. Mitigation: results are always reported with the
      environment attached, and no capacity claim is made from them.

  R5  Automated accessibility tooling detects only a portion of real barriers.
      Mitigation: a manual checklist accompanies every automated scan, and no
      claim of WCAG conformance is made on the strength of a passing scan.

  R6  The ParaBank database is wiped on container recreation. Mitigation:
      provisioning is scripted and gated by the readiness check.

## Assumptions

  A1  ParaBank remains available under the Apache 2.0 licence and its published
      Docker image continues to run on Apple Silicon.
  A2  The demo dataset structure stays stable across image updates.
  A3  Behaviour marked "assumed" in the requirements register reflects intended
      behaviour. Where testing shows otherwise, the register is corrected rather
      than a defect being invented.

## Dependencies

  Docker and Docker Compose
  Python 3.12 and the packages in requirements.txt
  Node.js, for Newman and axe tooling, introduced in Phases 3 and 5
  A Java runtime, for Apache JMeter only, introduced in Phase 5. Note that this
    is a runtime for a testing tool, not Java code written by this project.
  A free-tier Jira account, optional, with importable files as the fallback

## Entry criteria

Testing starts only when all of these hold:

  E1  The environment readiness check passes.
  E2  ParaBank is provisioned with schema and demo data.
  E3  The smoke suite passes.
  E4  The requirements register validates.
  E5  The build under test is identified and recorded.

## Exit criteria

Testing is complete when all of these hold:

  X1  Every planned test case has been executed or explicitly deferred with a
      recorded reason.
  X2  Every quality gate in quality-gates.yaml has been evaluated.
  X3  No open defect of Critical or High severity.
  X4  Reconciliation reports zero unexplained breaks.
  X5  The traceability matrix shows requirement coverage at or above the gate
      threshold.
  X6  The test summary report is produced from actual results.
  X7  A release decision of GO, CONDITIONAL GO or NO-GO has been recorded.

## Severity and priority

These are different things and interviewers ask about the difference.

  Severity is technical impact. How badly is the system broken.
  Priority is business urgency. How soon must it be fixed.

  Severity
    Critical  Money is wrong, customer data is exposed, or the system is
              unusable. No workaround.
    High      A core banking function is broken. A workaround may exist but is
              not acceptable for customers.
    Medium    A feature behaves incorrectly in a limited case, with a workaround.
    Low       Cosmetic or minor, with no functional impact.

  Priority
    P1  Fix immediately, blocks the release.
    P2  Fix before the release.
    P3  Fix in a following release.
    P4  Fix when convenient.

They vary independently, which is the point of having both:

  High severity, low priority   Data corruption in a feature nobody uses yet.
  Low severity, high priority   A spelling mistake in the bank's name on the
                                login page. Trivial to fix, embarrassing to
                                ship, so it goes out before the release.

## Quality gates

Defined in quality-gates.yaml and documented in docs/quality-gates.md. Five
gates fail the release outright, five allow a conditional release with a
recorded and accepted risk.
