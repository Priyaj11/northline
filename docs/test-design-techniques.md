# Formal test design techniques

Anyone can write tests. The question a QA engineer must answer is how they
decided which tests to write, and how they know there are enough. These six
techniques are the answer, and each one is applied to real inputs in this
project rather than only defined.

Every test case in test-cases/ records the technique that produced it.

## 1. Equivalence Partitioning

Divide the possible inputs into groups whose members should all behave the same
way, then test one representative from each group. Testing 50, 51 and 52 gains
nothing over testing 50 alone, because all three are ordinary positive amounts.

Applied to the transfer amount field:

  Partition                      Representative   Expected
  -----------------------------  ---------------  ------------------------
  Negative amounts               -500.00          rejected
  Zero                           0.00             rejected
  Positive, within balance       100.00           accepted
  Positive, above balance        balance + 500    behaviour unconfirmed
  Non-numeric                    abc              rejected

Cases: TC-XFER-001, TC-XFER-007, TC-XFER-015, TC-XFER-008.

## 2. Boundary Value Analysis

Defects cluster at edges, because edges are where a developer writes a greater
than sign when they meant greater than or equal to. Test either side of every
boundary, and the boundary itself.

Applied to the transfer amount, where the boundary is zero:

  Value    Position                Expected   Why it matters
  -------  ----------------------  ---------  --------------------------------
  -0.01    just below              rejected   catches a missing sign check
   0.00    the boundary            rejected   the boundary itself
   0.01    just above              accepted   catches >= where > was meant

The third value is the one nobody thinks to try, and the one that finds the bug.

Applied to the source balance, where the boundary is the balance itself:

  balance - 0.01, balance, balance + 0.01

Cases: TC-XFER-004, TC-XFER-005, TC-XFER-006, TC-XFER-015, TC-XFER-010.
Also applied to empty fields (TC-AUTH-006 to TC-AUTH-008), where the boundary
is zero characters, and to date range filtering (TC-TXN-003), where the
question is whether the range is inclusive.

## 3. Decision Table Testing

When several conditions combine to produce an outcome, enumerate them. Four
yes-or-no conditions give sixteen combinations, but most collapse, because once
the amount is invalid nothing else is examined.

Transfer decision table:

  Rule  Amount > 0  Source valid  Destination  Source not     Outcome
                    and owned     exists       destination
  ----  ----------  ------------  -----------  -------------  --------------------
  R1    No          any           any          any            reject, bad amount
  R2    Yes         No            any          any            reject, bad source
  R3    Yes         Yes           No           any            reject, unknown dest
  R4    Yes         Yes           Yes          No             same account, net
                                                              change must be zero
  R5    Yes         Yes           Yes          Yes            accept

Five rules rather than sixteen combinations, and every rule is a test case with
a stated reason for existing.

Cases: TC-XFER-013 covers R4, the rule most often forgotten.

## 4. State Transition Testing

Model the system as states and the events that move between them. Test the
valid transitions, and more importantly the invalid ones.

Session state model:

  From                     Event                              To
  -----------------------  ---------------------------------  -----------------
  Logged out               Valid login                        Logged in
  Logged out               Invalid login                      Logged out
  Logged out               Direct request for account page    Logged out, no data
  Logged in                Log out                            Logged out
  Logged in                Request an account page            Logged in
  Logged out after logout  Reuse the previous page address    Logged out, no data

Rows three and six are transitions that must NOT happen. Those are where
authorisation defects live, and they are invisible to anyone testing only the
happy path.

Cases: TC-AUTH-009, TC-AUTH-010, TC-SEC-006, TC-SEC-007, TC-ACC-005, TC-ACC-006.

## 5. Pairwise Testing

When combinations explode, note that most defects arise from an interaction
between two factors, not five. So cover every pair of values rather than every
combination.

Factors for a browser-based transfer:

  browser       Chromium, Firefox, WebKit
  account type  CHECKING, SAVINGS
  amount class  minimum valid, typical, maximum valid

Full combinations: 18. Distinct pairs to cover: 21.
Minimum set found by greedy pair coverage: 9 combinations.

  1  Chromium  CHECKING  minimum valid
  2  Chromium  SAVINGS   typical
  3  Firefox   CHECKING  typical
  4  Firefox   SAVINGS   minimum valid
  5  WebKit    CHECKING  maximum valid
  6  Chromium  SAVINGS   maximum valid
  7  WebKit    SAVINGS   minimum valid
  8  Firefox   CHECKING  maximum valid
  9  WebKit    CHECKING  typical

Verified: these nine cover all 21 pairs. Half the runtime, no meaningful loss.

The honest limitation: pairwise finds defects caused by two factors
interacting. A defect that only appears when all three specific values occur
together can be missed. That is an accepted trade, not an oversight.

Case: TC-XFER-016.

## 6. Negative Testing

Deliberately do the wrong thing and confirm the system refuses correctly,
rather than crashing, silently accepting, or leaking information.

Applied across the project:

  Malformed amounts        abc, $100, 1,000.00, 1e3, 10.005
  Missing data             empty username, empty password, empty amount
  Non-existent entities    account 99999999
  Unauthorised access      account data with no credentials
  Bypassed validation      a negative amount sent past the browser form
  Injected data faults     missing, duplicated and altered settlement records

One rule underpins all of it: a validation rule enforced only in the browser is
not enforced at all, because the service can be called directly. TC-SEC-008
exists to prove that point.

Cases: 19 in total, listed in the traceability matrix.

## Why the counts are uneven

Equivalence Partitioning and Negative Testing dominate because most requirements
concern whether an input class is handled correctly. Decision Table and Pairwise
each appear once, because each solves a specific problem: combining conditions,
and reducing an exploding matrix. Using a technique where it does not fit
produces test cases that look rigorous and prove nothing.
