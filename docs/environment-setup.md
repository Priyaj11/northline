# Environment setup and Phase 1 findings

## Starting the environment

    make up      # start ParaBank and the PostgreSQL certification data store
    make init    # provision ParaBank (create schema and demo data)
    make health  # verify readiness
    make smoke   # run the smoke tests

    make env     # all of the above, in order

## Ports

    8080   ParaBank web application and web services
    9001   ParaBank HyperSQL listener (exposed, unused by Northline)
    5433   Northline PostgreSQL certification data store (host side)

PostgreSQL listens on 5432 inside its container as always. Only the host side
moved to 5433, because another container on the development machine already
published 5432. A test framework must not assume it owns a well-known port.

## Finding 1: ParaBank ships with an empty database

Before provisioning, /parabank/index.htm answers 302 and redirects to
/parabank/initializeDB.htm, and every page fails with:

    org.hsqldb.HsqlException: user lacks privilege or object not found: PARAMETER

The PARAMETER table does not exist because the schema has not been created.
Visiting initializeDB.htm once creates the schema and loads demo data.

ParaBank's database lives inside the container with no mounted volume, so it is
wiped on every container recreation. Provisioning is therefore a scripted,
repeatable step (scripts/initialize_sut.py), not a manual one. Anything that
has to be remembered by a human will eventually be forgotten at 2am.

## Finding 2: liveness is not readiness

Liveness  - the process is running and answering on its port.
Readiness - the application is actually usable.

The original Docker healthcheck used `curl -f` against index.htm. Because
`curl -f` only fails on HTTP 400 and above, a 302 redirect counted as success.
Docker reported the container "healthy" for nine minutes while every page in
the application was failing with a database error.

Northline's own readiness check (scripts/healthcheck.py) now requires:

  1. index.htm returns 200 with redirects disabled. A 302 means unprovisioned.
  2. admin.htm returns 200. That page queries the Parameter table, so a 200
     is positive evidence that the schema exists.
  3. PostgreSQL accepts a connection and answers SELECT 1.

Quality gate: if readiness fails, no test suite runs and the release is NO-GO.

## Finding 3: a misleading error message

When the warehouse container failed to bind port 5432, it stayed in Docker
state `Created` with empty logs. The test client then connected to a different
PostgreSQL that happened to own that port, and failed with:

    FATAL: password authentication failed for user "northline"

The message pointed at credentials. The actual fault was a port collision and a
container that never started. Worth remembering when triaging: an error message
describes the symptom, not necessarily the cause.

## Local interpreter note

The development machine's shell resolves `python` to a system Python 3.9 ahead
of the virtual environment, so the Makefile invokes `.venv/bin/python`
explicitly rather than relying on shell activation.
