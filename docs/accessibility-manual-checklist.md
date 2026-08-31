# Manual accessibility checklist

Covers TC-ACC-005 and TC-ACC-006, and the parts of TC-ACC-007 a scanner cannot
decide.

## Why this exists

Automated scanning finds the machine-checkable subset of accessibility
barriers, commonly estimated at around a third of the total. axe-core can tell
you a field has no label. It cannot tell you whether the tab order makes sense,
whether a focus indicator is actually perceivable, or whether an error message
is intelligible to somebody who cannot see the field it refers to.

The findings in DEF-003 and DEF-004 came from the automated scan. Everything
below requires a person, and none of it has been executed yet. The result
column is blank on purpose. A checklist filled in without performing the checks
is worse than no checklist, because it looks like evidence.

## How to run it

Use a keyboard only. Put the mouse aside; do not use it to scroll, click or
focus anything. Record what happens, including where it works.

For the screen reader items on macOS, VoiceOver is built in and starts with
Command + F5.

## TC-ACC-005  Complete a login using the keyboard alone

| # | Check | Expected | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | Tab from page load reaches the username field | Reachable without a mouse | | |
| 2 | Focus is visible at every step | A clearly perceivable indicator | | |
| 3 | Tab order follows the visual order | Username, then password, then Log In | | |
| 4 | Enter submits the form from either field | The form submits | | |
| 5 | After a failed login, focus lands somewhere useful | Focus moves to the error or back to the form | | |
| 6 | The error message is announced by a screen reader | Announced, not only shown in red | | |

## TC-ACC-006  Complete a transfer using the keyboard alone

| # | Check | Expected | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | Reach the transfer page by keyboard from the overview | Reachable | | |
| 2 | The amount field is reachable and its purpose is announced | Announced meaningfully | | |
| 3 | Both account dropdowns are operable by keyboard | Openable and selectable | | |
| 4 | The selected account is announced when it changes | Announced | | |
| 5 | The Transfer button is reachable and activates by Enter or Space | Activates | | |
| 6 | The confirmation is announced or reachable after submission | Reachable without a mouse | | |
| 7 | Focus is visible throughout | A clearly perceivable indicator | | |

## TC-ACC-007  Validation errors are not conveyed by colour alone

| # | Check | Expected | Result | Notes |
| --- | --- | --- | --- | --- |
| 1 | Submit an invalid amount and read the error | Text states what is wrong | | |
| 2 | The error is associated with the field in the markup | aria-describedby or equivalent | | |
| 3 | The error is conveyed by more than colour | Text or icon as well as colour | | |
| 4 | A screen reader announces the error without moving to it | Announced on appearance | | |

## Known context before starting

DEF-003 records that 28 form controls have no accessible name. Several checks
above will therefore fail for that reason. Record what actually happens rather
than assuming the outcome, because the manual pass may find things the scanner
did not, and may find that something works better than expected.

## Result

Not yet executed. No claim is made about the outcome of any check above.
