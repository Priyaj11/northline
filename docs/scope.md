# Scope

## In scope

Functional areas of ParaBank under test:

  Authentication   login, logout, registration, invalid and empty credentials
  Accounts         account list, account detail, opening an account
  Funds transfer   valid transfers, invalid amounts, unknown destinations
  Bill payment     valid payment, invalid payee details
  Transactions     history, filtering, record structure

Testing types applied:

  Functional testing through the browser interface
  Application programming interface testing
  Database and data validation
  Settlement reconciliation
  Accessibility to WCAG 2.1 level AA
  Performance under small realistic load
  Security-adjacent behaviour
  Regression and smoke suites
  Release certification

## Out of scope

  Building or modifying ParaBank. It is the system under test, not our code.
  Penetration testing, exploitation, or any offensive security work.
  Mobile applications and native clients. ParaBank has none.
  Load testing beyond a small realistic profile. This runs on one laptop.
  Loan processing and the stock position features. Present in the application
    but not core retail banking, and out of scope to keep the project small
    enough for one person to understand completely.
  SOAP service testing. The SOAP interface exists and is noted in
    docs/sut-parabank.md, but the REST interface covers the same functionality
    and testing both would add breadth without adding skill.
  Cloud deployment, Kubernetes, and multi-environment promotion.
  Any feature requiring a paid account. Jira integration is best effort with
    importable files as the documented fallback, so the project never breaks
    because a free tier changed.

## Why the out-of-scope list matters

An untested area is only a risk when nobody knows it is untested. Writing the
exclusions down turns a silent gap into a stated one, which is the difference
between a considered scope and an accident.
