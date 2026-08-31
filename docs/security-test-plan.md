# Security-adjacent test plan

## Scope, and what is deliberately outside it

Northline verifies that ParaBank enforces the access rules it claims to
enforce. That is testing a control.

It does not attempt to exploit anything, does not enumerate identifiers beyond
what a single request reveals, does not retain any data read during a test, and
does not attempt privilege escalation, injection, denial of service or any
other offensive technique. That would be penetration testing, which requires
authorisation, a defined rules of engagement document, and a different skill
set. It is out of scope, and saying so is more useful than pretending otherwise.

Where a control is found missing, the evidence recorded is one request and its
outcome. That is what a defect report needs, and it is where the testing stops.

## What was tested

    Test case   Check                                       Layer     Result
    ---------   -----------------------------------------   -------   ----------
    TC-SEC-001  Account data requires authentication        service   FAIL
    TC-SEC-002  Transaction data requires authentication    service   FAIL
    TC-SEC-003  Cross-customer account access is refused    service   FAIL
    TC-SEC-005  Credentials are not carried in the URL      service   FAIL
    TC-SEC-008  Amount validation is enforced server side   service   FAIL
    TC-SEC-006  Protected pages need a session (3 pages)    browser   PASS
    TC-SEC-004  Logging out ends the session                browser   PASS
    TC-SEC-007  The session cookie is HttpOnly              browser   PASS
    TC-SEC-007  Discarding the cookie ends access           browser   PASS

Executed 2026-08-31 against the local environment.

## The pattern in those results

Every failure is on the service layer. Every pass is on the browser layer.

ParaBank has two channels into the same data. The browser channel enforces
sessions correctly. The service channel enforces nothing at all. This is a
common real-world shape: controls get applied where developers are thinking
about users, and omitted where they are thinking about integrations.

It also means a security assessment that only exercised the web interface would
have concluded the application was sound.

## Defects raised

    DEF-005  Critical  P1  The REST services require no authentication
    DEF-006  High      P2  Credentials are carried in the URL path
    DEF-001  Critical  P1  The transfer amount is not validated (raised in Phase 3B,
                           confirmed here from the server-side validation angle)

TC-SEC-001, TC-SEC-002 and TC-SEC-003 were filed as a single defect rather than
three. They share one root cause: with no authentication there is no requester,
so there can be no check that a record belongs to one. Three entries for one
problem would give a team no way to prioritise.

## What was not tested, and why

  Session timeout          ParaBank exposes no way to trigger or configure a
                           server-side timeout, so it cannot be tested on
                           demand. What was tested instead is that the session
                           cookie is what grants access: discard it and access
                           stops.

  Transport security       The local environment is served over plain HTTP, so
                           the Secure cookie attribute cannot be expected and
                           certificate handling cannot be assessed. Recorded
                           rather than asserted.

  Injection, escalation,   Out of scope as stated above.
  denial of service

  Password storage         Not observable through any interface available to
                           this framework.

## A note on the social security number field

The customer record returned by the login endpoint includes an ssn field. The
data is fabricated demonstration data belonging to a demonstration application,
and none of it is copied into this repository. It is noted because it widens
the impact of DEF-005: the unauthenticated exposure is not limited to financial
records.
