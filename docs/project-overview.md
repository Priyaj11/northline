# Northline: project overview

## What it is

Northline is an enterprise-style banking release certification framework. It is
a test framework, not a banking application.

## The problem

Before a bank releases a new version of its banking application, someone has to
decide whether it is safe to ship. That decision needs evidence from several
directions at once: does the interface work, does the service layer honour its
contract, did the money actually move, does it reconcile against settlement, can
customers with disabilities use it, does it hold up under load, and is customer
data properly protected.

Most portfolio test projects answer only the first of those, and stop at "the
screen said success". In banking that is the least trustworthy evidence
available.

## The solution

Northline tests a real banking application end to end, from the browser through
the service layer into the data and out into a settlement extract, then applies
configurable quality gates to the actual results and produces a release
decision of GO, CONDITIONAL GO or NO-GO.

## The System Under Test

ParaBank, a demonstration retail banking application published by Parasoft under
the Apache 2.0 licence, running from its official Docker image. Northline does
not include, modify or redistribute it. See NOTICE.md and docs/sut-parabank.md.

## What makes it more than a test suite

  It validates money movement in the data, not just on the screen.
  It reconciles a settlement extract and proves it detects four classes of break
    by deliberately injecting each one.
  It carries the full QA process, not only the automation: strategy, plan,
    formally derived test cases, traceability, defect management and a release
    decision.
  It generates its documentation from sources of truth where it can, so the
    documentation cannot quietly drift away from reality.
  It states its limitations rather than hiding them.

## Documentation map

  project-overview.md                 this document
  architecture.md                     how the pieces fit together
  scope.md                            what is and is not tested, and why
  requirements.md                     generated from requirements.yaml
  test-strategy.md                    how testing is approached
  test-plan.md                        what will be done and when
  test-data-strategy.md               keeping test data trustworthy
  quality-gates.md                    the thresholds and their rationale
  release-process.md                  how the release decision is reached
  sut-parabank.md                     the system under test and its quirks
  sut-endpoints.md                    generated from the running application
  environment-setup.md                running it, and Phase 1 findings
  requirements-traceability-matrix.md generated in Phase 2C
  accessibility-report.md             produced in Phase 5
  security-test-plan.md               produced in Phase 5
