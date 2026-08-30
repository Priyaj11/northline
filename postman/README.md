# Postman collection

Six requests, 22 assertions, covering ParaBank's read endpoints and two
contract checks.

## Why this exists alongside the pytest suite

It overlaps deliberately.

  - It runs anywhere Node.js is available, with no Python environment.
  - It is readable by people who do not write Python, which in a bank includes
    business analysts and manual testers.
  - Postman and Newman are named explicitly in most bank QA job descriptions.

It does not duplicate the transfer boundary analysis. Those assertions live in
tests/api/test_transfer_api.py where the money comparisons are, because Decimal
arithmetic matters there and JavaScript has no fixed-point number type.

## Running it interactively

Import both files into Postman:

    postman/northline.postman_collection.json
    postman/northline.local.postman_environment.json

Select the "Northline local" environment and run the collection. Requests must
run in order, because each one stores identifiers the next one uses.

## Running it headlessly with Newman

    npm install --global newman
    make newman

Or directly:

    newman run postman/northline.postman_collection.json \
      -e postman/northline.local.postman_environment.json \
      --reporters cli,junit \
      --reporter-junit-export reports/newman-junit.xml

## Notes

Every request sets Accept: application/json. ParaBank content-negotiates and
returns XML by default, so without that header every JSON assertion fails for a
reason that looks like a defect and is not. Recorded as Observation 7 in
docs/sut-parabank.md.

The transfer request moves one cent between two of the demo customer's own
accounts. Run `make reset` first if you want the seeded balances back.

The DEF-002 assertion deliberately asserts the broken behaviour, so it turns
red if the defect is ever fixed. That is the Newman equivalent of a strict
expected failure.
