# System Under Test: ParaBank

## What it is
ParaBank is a demonstration retail banking web application published by
Parasoft. It offers customer registration, login, account overview, funds
transfer, bill payment, loan requests, and transaction history, and it exposes
the same functionality through web services.

## Licence
Apache License 2.0. Source: https://github.com/parasoft/parabank
See NOTICE.md at the repository root for the attribution statement.

## How Northline runs it
Official Docker image `parasoft/parabank`, started through docker-compose.yml.

  Start:   docker compose up -d
  Stop:    docker compose down
  Logs:    docker compose logs -f parabank
  Health:  curl -I http://localhost:8080/parabank/index.htm

## Ports
  8080   Web application and web services
  9001   HyperSQL database listener (exposed but unused by Northline)
  61616  Java messaging endpoint for the loan processor (not exposed)

## Default demo credentials
  username: john
  password: demo

## Database
ParaBank stores its data in HyperSQL, an in-process database written in Java.
Reaching it from Python requires a Java Database Connectivity bridge and a Java
runtime, which this project deliberately avoids.

Northline therefore runs its own PostgreSQL certification data store, extracts
account and transaction data from ParaBank's web services, and performs all SQL
validation and settlement reconciliation there. This mirrors how a real bank
feeds a reconciliation engine from a core banking extract.

## Known limitation
Northline validates the system of record as exposed through ParaBank's API,
not ParaBank's raw internal tables. This is stated in the README rather than
hidden.

## Discovered endpoints
(To be filled in from real output during Phase 1 discovery. Nothing is recorded
here that has not been observed against a running instance.)

## Discovered interfaces (observed 2026-08-29 against a running instance)

REST services base:  http://localhost:8080/parabank/services/bank
WADL description:    http://localhost:8080/parabank/services/bank?_wadl
SOAP description:    http://localhost:8080/parabank/services/ParaBank?wsdl  (returns 200)
UI JSON path:        http://localhost:8080/parabank/services_proxy/bank/... (returns 401)

The generated endpoint list lives in docs/sut-endpoints.md.

Data model declared in the WADL: customer, address, account, transaction,
payee, billPayResult, position, historyPoint, loanResponse.

Verified calls:
  GET /services/bank/login/john/demo                  -> 200
  GET /services/bank/customers/12212/accounts         -> 200, JSON array

Demo customer 12212 has 11 accounts, mostly CHECKING with two SAVINGS.

## Two observations to carry into later phases

### Observation 1: the REST services are unauthenticated
The accounts call above was made with no credentials, no cookie and no token,
and returned every account and balance for customer 12212. Any client that can
reach the server can read any customer's financial data by guessing a customer
identifier. In banking terms this is a Broken Object Level Authorization
weakness.

This may be deliberate in a demo application. It is recorded here as an
observation, not yet as a defect. Phase 5 tests it, Phase 6 writes it up with
evidence if it holds.

Practical consequence for Northline: the API test suite in Phase 3 does not
need a login flow to read data. The session-authenticated /services_proxy/
path, which returns 401, is what the browser UI uses after login.

### Observation 2: negative balances in the seeded data
Account 12345 (CHECKING) is at -2300.00 and account 12678 (SAVINGS) is at
-100.00 in the freshly initialised demo data. Useful raw material for boundary
value analysis in Phase 2, and a possible defect depending on what the
application's own rules say about overdrafts.

## Endpoints that shape Northline's design

Full generated list: docs/sut-endpoints.md (27 resource paths).

### Provisioning and test data reset
  POST /services/bank/initializeDB   creates schema and demo data
  POST /services/bank/cleanDB        wipes the data

Together these give a deterministic reset: clean, initialise, run. This matters
more than it looks. A transfer test that runs twice against the same data sees
different balances the second time, so without a reset the suite is only
trustworthy on a fresh container. Phase 3 and Phase 4 build on these.

### Money movement (Phase 4 reconciliation)
  POST /services/bank/transfer
  POST /services/bank/deposit
  POST /services/bank/withdraw
  POST /services/bank/billpay

### Reading state (Phase 3 and Phase 4 assertions)
  GET  /services/bank/customers/{customerId}
  GET  /services/bank/customers/{customerId}/accounts
  GET  /services/bank/accounts/{accountId}
  GET  /services/bank/accounts/{accountId}/transactions
  GET  /services/bank/accounts/{accountId}/transactions/amount/{amount}
  GET  /services/bank/accounts/{accountId}/transactions/fromDate/{fromDate}/toDate/{toDate}
  GET  /services/bank/transactions/{transactionId}

### Application configuration
  POST /services/bank/setParameter/{name}/{value}

## Observation 3: credentials are passed in the URL path

  GET /services/bank/login/{username}/{password}

A Uniform Resource Locator is recorded in server access logs, browser history,
proxy logs and referrer headers. Passing a password in the path leaks it in
plain text into several places that are not treated as secret stores. Recorded
as an observation for Phase 5; written up as a defect in Phase 6 only if it
still holds after testing.

There is also no logout endpoint in the REST interface. Session termination is
a browser-side concern only, which constrains what Phase 5 can test about
session timeout through the API.

## Observation 4: response contract inconsistencies (Phase 3A discovery)

Recorded from docs/sut-api-shapes.md, generated against the running instance.

  Endpoint                       Status  Declared type    Body actually is
  -----------------------------  ------  ---------------  -------------------
  /login/{user}/{pass}           200     application/json JSON
  /customers/{id}/accounts       200     application/json JSON
  /accounts/{id}                 200     application/json JSON
  /accounts/{id}/transactions    200     application/json JSON
  /transfer                      200     application/json PLAIN ENGLISH TEXT
  /accounts/99999999             400     text/plain       plain text

Two problems.

The transfer endpoint declares application/json and returns a sentence:
"Successfully transferred $0.01 from account #12345 to account #12456".
A client that trusts the declared content type and calls a JSON parser crashes.
This is a genuine contract defect and is written up with evidence in Phase 6.

Error responses use text/plain regardless of the Accept header, so every
assertion must check the status before attempting to parse a body.

## Observation 5: the transaction date is an integer

The date field on a transaction is an integer, not a formatted date string,
almost certainly epoch milliseconds. Consequences: type assertions must expect
a number, plausibility must be checked by converting rather than parsing, and
the date range filter's expected input format has to be established separately.

## Observation 6: the login response includes a social security number field

The customer record returned by the login endpoint carries an ssn field. The
data is fabricated, but the shape matters given that the same service layer was
observed in Phase 1 to require no authentication. Recorded for Phase 5.

## Observation 7: the services content-negotiate

The REST endpoints return XML by default and JSON only when the client sends
an Accept: application/json header.

    curl -s .../accounts/12345
      -> <?xml version="1.0"?><account><id>12345</id>...

    curl -s -H "Accept: application/json" .../accounts/12345
      -> {"id":12345,"customerId":12212,...}

Northline's API client sets the JSON Accept header for every request, which is
why docs/sut-api-shapes.md records JSON structures.

Consequence for Phase 3B: the Postman collection must set the same header
explicitly. Without it, every JSON assertion fails against an XML body, which
looks like a defect and is not.

## Observation 8: no username enumeration on the login form (positive finding)

TC-AUTH-005 verified in Chromium on 2026-08-30 that the browser login form
returns the same error message for a valid username with a wrong password as it
does for a username that does not exist.

Differing messages would let an attacker confirm which usernames exist by
reading the response, which is username enumeration. ParaBank does not have
that weakness on this form.

Recorded because a verification that passes is evidence too. A record showing
only defects gives no signal about what was actually checked.

## Observation 9: no cross-browser differences found (positive finding)

Run on 2026-08-30. The 14 functional browser tests were executed in Chromium,
Firefox and WebKit. All 42 executions passed, with no behavioural differences
between engines.

Cross-browser problems usually surface in form control behaviour, date handling
and layout-dependent waits. ParaBank's markup is plain enough that none of those
differ here.

The visual baselines are stored per browser, because font rendering and form
control appearance do differ between engines even where behaviour does not. A
baseline from one browser is not valid for another.

Recorded because a verification that passes is evidence too, and because
claiming cross-browser coverage is only honest if it has actually been run.

## Observation 10: the seeded demo data contains self-contradictory records

Established by experiment on 2026-08-30, not assumed.

Four seeded transactions have a type that contradicts their own description:

    id     account  type   amount    description
    13699  12345    Debit     0.00   Funds Transfer Sent
    13810  13122    Debit     0.00   Funds Transfer Received
    14032  13233    Debit   100.00   Funds Transfer Received
    14365  13344    Debit  1000.00   Funds Transfer Received

Three are described as received but typed as a debit. Any downstream system
that sums by type rather than by description gets a wrong total for those
accounts. Two also carry an amount of 0.00, even though TC-XFER-004 confirmed
the application rejects a transfer of zero.

## Why this is NOT recorded as a defect

The obvious conclusion would be that ParaBank writes transaction records
incorrectly. That conclusion is wrong, and the experiment that settled it was:

  1. Reset with cleanDB plus initializeDB, extract, run the query. The same four
     records appear with the same identifiers, so they come from the seed.
  2. Perform a live transfer of 42.00 from account 12567 to account 12789,
     extract, inspect the two records the application just wrote:

         12567  Debit   42.00  Funds Transfer Sent
         12789  Credit  42.00  Funds Transfer Received

     Correct on both sides.

The application writes correct records today. The inconsistency is a property
of the demo dataset shipped with the image, not of the code under test.

Recording it as a defect would have been an overclaim, and one that anyone
running the same two commands could disprove. The general point: when data
looks wrong, establish whether the system produced it or inherited it before
writing anything down.

## What was done instead

tests/database/test_data_quality.py takes a baseline of the existing
inconsistencies, performs a transfer, and asserts that no NEW inconsistency
appeared. It also asserts positively that a transfer writes a matched
Debit/Sent and Credit/Received pair for the same amount.

Asserting perfection against a known-imperfect starting state produces a
permanently red suite that everyone learns to ignore. Asserting "no worse than
the baseline" keeps the check meaningful.

## Transaction vocabulary observed

    types:        Credit, Debit
    descriptions: Funds Transfer Sent, Funds Transfer Received,
                  Bill Payment to <payee>, Check # <number>

## Correction to Observation 10, 2026-08-30

Observation 10 stated that two seeded transactions carry an amount of 0.00
"even though TC-XFER-004 confirmed the application rejects a transfer of zero".

That parenthetical was wrong. The application does NOT reject a transfer of
zero. See the amendment to DEF-001: a transfer of 0.00 returns 200 and writes a
record on both accounts.

The zero-amount seeded records are therefore not anomalies at all. They are
exactly what a zero-amount transfer produces, and their presence in the seed is
consistent with the application's actual behaviour.

The type-versus-description contradictions in Observation 10 stand unchanged.
Those were established by experiment and remain seed-only.
