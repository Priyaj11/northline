# Architecture

## The two halves

    ParaBank (System Under Test)              Northline (test framework)
    +----------------------------+            +------------------------------+
    |  Browser user interface    | <--------- |  Playwright + Page Objects   |
    |  REST services             | <--------- |  requests, Postman, Newman   |
    |  SOAP services (unused)    |            |  JMeter                      |
    |  HyperSQL (internal)       |            |                              |
    +----------------------------+            |  extract accounts and        |
                |                             |  transactions via REST       |
                +---------------------------> |            |                 |
                                              |            v                 |
                                              |  PostgreSQL certification    |
                                              |  data store                  |
                                              |    - SQL validation          |
                                              |    - settlement reconciliation|
                                              |            |                 |
                                              |            v                 |
                                              |  Certification engine        |
                                              |  GO / CONDITIONAL GO / NO-GO |
                                              +------------------------------+

## Why a separate certification data store

ParaBank stores its data in HyperSQL, a database written in Java and reachable
only through a Java Database Connectivity bridge, which would mean adding a Java
runtime to a Python project.

Northline therefore runs its own PostgreSQL database, extracts account and
transaction data from ParaBank's REST services, and performs all SQL validation
and settlement reconciliation there.

This is not only a way around the Java problem. It is how banks actually work:
the core banking system owns its own database, and the reconciliation and
settlement engine reads an extract of it rather than querying the core directly.

Stated limitation: Northline validates the system of record as exposed through
the application's interface, not ParaBank's raw internal tables. This is
recorded in the README rather than hidden.

## Layers and what each one catches

    Layer            Catches
    ---------------  --------------------------------------------------------
    Smoke            an environment that is not fit to test at all
    User interface   broken screens, broken navigation, broken validation
    API              broken contracts, wrong status codes, wrong data types
    Database         a screen that says success while the data says otherwise
    Reconciliation   money that does not add up across systems
    Accessibility    an interface unusable by people relying on assistive tech
    Performance      correct behaviour that is too slow to be usable
    Security         data reachable by someone who should not reach it
    Certification    a release that should not ship

Every layer exists because it catches a class of defect the layers above and
below it cannot. That is the test for whether a layer earns its place.

## Repository layout

    docs/             QA documentation, some generated, some written
    test-cases/       formally derived test cases
    tests/            the automated suites, split by type
    pages/            Playwright page objects
    fixtures/         shared pytest fixtures
    utils/            configuration, logging, shared helpers
    database/         SQL and data validation helpers
    reconciliation/   settlement generation and reconciliation engine
    certification/    the release decision engine
    postman/          Postman collection run through Newman
    performance/      JMeter test plan
    defects/          defect reports, real ones only
    reports/          generated output, not committed
    scripts/          provisioning, discovery, generation, health
    .github/workflows CI pipelines
