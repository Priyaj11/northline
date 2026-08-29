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
