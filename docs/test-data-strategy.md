# Test Data Strategy

## The problem

A transfer test moves 100 from account A to account B and asserts the balances.
Run it a second time and the balances differ, so the assertion fails even
though nothing is broken. Test data that changes underneath tests is one of the
most common causes of a suite nobody trusts.

Three things solve it: reset, isolate, or assert on change rather than value.
Northline uses all three, choosing per suite.

## What ParaBank gives us

Discovered from the service description in Phase 1:

  POST /services/bank/cleanDB        wipes application data
  POST /services/bank/initializeDB   creates schema and seeds demo data

Together these are a deterministic reset. This is unusually generous; most
systems under test have nothing equivalent, and the reconciliation and
transfer suites depend on it.

## Seeded data

Demo customer 12212 (username john, password demo) owns 11 accounts, mostly
CHECKING with two SAVINGS. Balances in the seeded set include negative values,
notably a CHECKING account at -2300.00 and a SAVINGS account at -100.00. Those
are used as boundary inputs in Phase 2C test design, and may themselves be a
defect depending on the application's stated rules.

Exact identifiers are not written into tests. They are read at runtime from the
customer accounts endpoint, because hard-coded identifiers break the moment the
seed changes.

## Three approaches, and when each is used

  1. Reset before the suite
     Wipe and reseed, then run. Used by the reconciliation suite and the
     database validation suite, where absolute values must be predictable.
     Cost: slow, and it cannot run in parallel with anything else.

  2. Create isolated data per test
     Register a fresh customer with its own accounts, then operate only on
     those. Used by transfer and bill payment tests. Tests become independent
     of each other and safe to run in parallel, which matters most as the suite
     grows.
     Cost: registration must work, so it is itself covered by REQ-AUTH-005.

  3. Assert on deltas, not absolutes
     Read the balance, act, read again, assert the difference is exactly the
     amount transferred. Used wherever possible because it is robust to any
     starting state.
     Cost: it cannot catch a wrong starting balance, so it complements the
     other two rather than replacing them.

## Rules

  No test depends on another test having run first.
  No test asserts an absolute balance unless it reset or created that data.
  No account identifier is hard-coded. Identifiers are read at runtime.
  Any test that changes money either creates its own data or runs after a reset.
  Amounts are chosen from the boundary analysis in Phase 2C, not picked at random.

## Sensitive data

ParaBank's demo dataset contains fields shaped like personal data, including a
social security number field on the customer record. It is fabricated demo data
belonging to a demonstration application, not real personal information, and
none of it is copied into this repository. Generated test data uses obviously
fake values.

In a real bank this section would describe production data masking, and the rule
would be absolute: production customer data never enters a test environment.
