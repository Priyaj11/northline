# Test Plan

Release: R1.0
System Under Test: ParaBank
Environment: local
Prepared by: Northline

The strategy in docs/test-strategy.md says how testing is approached. This plan
says what will be done, in what order, and how it will be judged.

## Features to be tested

  Authentication      REQ-AUTH-001 to REQ-AUTH-005
  Accounts            REQ-ACCT-001 to REQ-ACCT-004
  Funds transfer      REQ-XFER-001 to REQ-XFER-006
  Bill payment        REQ-BILL-001 to REQ-BILL-003
  Transaction history REQ-TXN-001 to REQ-TXN-003
  Data integrity      REQ-DATA-001 to REQ-DATA-004
  Security-adjacent   REQ-SEC-001 to REQ-SEC-004
  Accessibility       REQ-ACC-001 to REQ-ACC-003
  Performance         REQ-PERF-001 to REQ-PERF-003

## Features not to be tested

Loan processing, stock positions, the SOAP interface, and the bookstore
application bundled in the container. Reasons are recorded in docs/scope.md.

## Approach by phase

  Phase 3  Automation framework, browser tests, API tests, Postman and Newman
  Phase 4  Database validation, transaction correctness, reconciliation
  Phase 5  Accessibility, security-adjacent behaviour, performance
  Phase 6  Defect management, test management, continuous integration
  Phase 7  Release certification and the summary report

## Test suites and when each runs

  Suite            Marker            Pull request   Nightly
  ---------------  ----------------  -------------  -------
  Smoke            smoke             yes            yes
  API              api               yes            yes
  UI               ui                subset         full
  Database         database          no             yes
  Reconciliation   reconciliation    no             yes
  Accessibility    accessibility     subset         full
  Security         security          no             yes
  Performance      -                 no             yes

Pull request runs stay short so they give feedback while the change is still
fresh in the author's mind. The nightly run buys thoroughness with time nobody
is waiting on.

## Pass and fail criteria

A test case passes when its expected result is observed exactly. Partial
matches are failures. A suite is judged against the relevant gate in
quality-gates.yaml, not against opinion.

## Suspension and resumption criteria

Testing is suspended when:

  The environment readiness check fails.
  The smoke suite fails.
  A Critical defect blocks a core workflow, making further results unreliable.

Testing resumes when the blocking condition is resolved and the smoke suite
passes again.

## Deliverables

  requirements.yaml and docs/requirements.md
  docs/test-strategy.md and this plan
  test-cases/ with formally derived cases
  docs/requirements-traceability-matrix.md, generated
  Automated suites under tests/
  reports/ with test results, reconciliation report and accessibility report
  defects/ with real defect reports only
  The release certification decision and test summary report

## Responsibilities

Single engineer project. All roles are held by one person, which is stated
plainly rather than dressed up as a team structure.

## Schedule

Phase ordered rather than date ordered. Each phase completes and is verified
before the next begins.

## Approvals

No external approver exists for this project. The certification decision is
produced mechanically by the engine in Phase 7 from real results, which is a
deliberate substitute for a sign-off that cannot be genuine here.
