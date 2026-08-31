# Test management: how Northline maps to Jira

## The direction of truth

Northline's registers are the source of truth. Jira is an export target.

    requirements.yaml   ->  Story issues
    test-cases/*.yaml   ->  Test issues
    defects/register.yaml -> Bug issues

Not the other way round, and that is deliberate.

A project that keeps its requirements inside a Jira free tier stops working the
day the tier changes, and cannot be reviewed by anybody without an account.
Keeping the registers in the repository means they are version controlled,
diffable in a pull request, validated by a script that fails the build, and
readable by anyone who can read the repository.

Mature teams often work this way with requirements-as-code for exactly these
reasons. The export exists so that a team already living in Jira can adopt the
project without rekeying anything.

## Project structure

    NORTHLINE (project key: NL)
    |
    +-- Epic          one per requirement area: ENV, AUTH, ACCT, XFER, BILL,
    |                 TXN, DATA, SEC, ACC, PERF
    |
    +-- Story         one per requirement, parented to its area epic
    |                 REQ-XFER-003 "A transfer of zero or a negative amount is rejected"
    |
    +-- Test          one per test case, linked to the requirement it covers
    |                 TC-XFER-005 "Reject a transfer just below zero"
    |
    +-- Bug           one per defect, linked to the requirement it violates and
    |                 to the test cases that found it
    |                 DEF-001 "Transfer amounts are not validated"
    |
    +-- Task          environment and framework work with no requirement behind it

## Issue links used

    Story  <- tests -      Test    a test case verifies a requirement
    Bug    <- blocks -     Story   a defect violates a requirement
    Bug    <- is found by -Test    a test case raised the defect
    Epic   <- parent of -  Story   an area contains its requirements

Those four links reproduce the traceability chain the matrix already shows:
requirement to test case to automation to defect to result.

## Fields carried across

    Jira field        Source
    ---------------   -------------------------------------------------
    Summary           title
    Description       detail, or for a test the full steps and expected
    Priority          priority, mapped for bugs from severity
    Labels            source, technique, automation status, detection layer
    Fix Version       release
    Linked Issue      the requirement or test case identifiers

Severity maps to Jira's priority field for bugs:

    Critical -> Highest      High -> High
    Medium   -> Medium       Low  -> Low

That mapping loses information, and it is worth knowing why. Jira has one
priority field by default, while Northline records severity and priority as
separate values because they are different things and vary independently. A
real Jira project would add a custom field for severity rather than collapsing
the two. The export uses the default field so the files import into an
unmodified project; the separation survives in the labels.

## Generating the import files

    make jira

Writes into reports/jira/:

    epics.csv         10 rows
    requirements.csv  41 rows
    tests.csv         72 rows
    defects.csv        6 rows

Import all four in a single pass. Jira's CSV importer resolves the Issue ID and
Parent ID columns within one import, so splitting them across separate imports
breaks the hierarchy.

## Test execution and cycles

Jira alone has no concept of a test run. That comes from Xray or Zephyr, and
both are paid applications with trial periods.

Rather than making the project depend on a trial, execution results stay where
they are produced:

    reports/junit.xml                    pytest, every suite
    reports/newman-junit.xml             the Postman collection
    reports/performance-report.json      JMeter analysis
    reports/reconciliation-report.json   settlement reconciliation
    reports/defects.json                 the defect register

Both JUnit XML files are the standard machine-readable test result format. Xray
and Zephyr both import it directly, as do most continuous integration systems,
so a team with either tool can attach these results to a test cycle without
Northline needing to know that tool exists.

## What was NOT done, and why

No screenshots of a Jira board appear in this repository, and no Jira instance
was populated to produce evidence.

Creating a project, importing the files and screenshotting the result would
demonstrate that the CSV files import cleanly, which is worth something. It
would not demonstrate anything about the testing, and a screenshot of a board
somebody filled in specifically to be screenshotted is decoration rather than
evidence.

The generated CSV files are the honest artefact: they are produced from the
real registers, they are regenerated whenever those change, and anybody with a
Jira instance can import them and see the structure for themselves.
