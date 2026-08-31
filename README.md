# Northline

**An enterprise banking release certification framework.**

Northline is a test framework, not a banking application. It exercises a real
banking application end to end, from the browser through the service layer into
the data and out into a settlement extract, then applies configurable quality
gates to the actual results and produces a release decision.

Its current decision on the application under test is **NO-GO**, and this is why:

```
    DECISION: NO-GO          8 of 10 gates passed

    GATE-CRITICAL-DEFECT     FAIL    5 open Critical or High defects, threshold 0
    GATE-ACCESSIBILITY       FAIL    26 critical or serious violations, threshold 0
    GATE-ENV                 PASS    environment ready
    GATE-SMOKE               PASS    0 failures
    GATE-RECON               PASS    0 settlement breaks
    GATE-API-PASS            PASS    100 percent
    GATE-UI-PASS             PASS    100 percent
    GATE-PERF-P95            PASS    191 ms, threshold 2000
    GATE-PERF-ERROR          PASS    0 percent, threshold 1
    GATE-COVERAGE            PASS    100 percent requirement coverage
```

Every suite passes at 100 percent and the release is still blocked. Anybody
reading only the pass rates would conclude the application is fine. The defect
register is what stops that, and the gate reads the register rather than the
test results for exactly that reason.

Full decision with the evidence file behind every figure:
[docs/release-certification.md](docs/release-certification.md)

## What it found

Eight defects in the application under test, none of which existed as a known
issue beforehand.

| ID | Severity | Finding |
| --- | --- | --- |
| [DEF-001](defects/DEF-001.md) | Critical | Transfer amounts are not validated. Negative amounts move money in reverse; zero amounts write empty records; `1e3` is parsed as 1000. |
| [DEF-007](defects/DEF-007.md) | Critical | A transfer of `10.005` leaves accounts the application **cannot read**. Every later request returns HTTP 500. Recoverable only by destroying all data. |
| [DEF-005](defects/DEF-005.md) | Critical | The REST services require no authentication. Any client that can reach the server can read any customer's accounts, balances and transactions. |
| [DEF-003](defects/DEF-003.md) | High | 28 form controls have no accessible name. A screen reader user cannot complete a transfer. |
| [DEF-006](defects/DEF-006.md) | High | Credentials are carried in the URL path, so passwords reach access logs, proxy logs and browser history in plain text. |
| [DEF-002](defects/DEF-002.md) | Medium | The transfer endpoint declares JSON and returns plain text. |
| [DEF-004](defects/DEF-004.md) | Medium | Page-level accessibility failures on every page. |
| [DEF-008](defects/DEF-008.md) | Medium | The transaction date search validates the shape of a date but not its values, and accepts `31-12-2026` silently. |

**DEF-007 is the one worth reading.** The application accepts a transfer amount
with three decimal places, stores a balance at that precision, and then throws
`ArithmeticException: Rounding necessary` on every subsequent read of those
accounts. It writes a value it cannot read back. It was found by a boundary
value case on decimal precision, which is not a test most people think to write.

## The system under test

[ParaBank](https://github.com/parasoft/parabank), a demonstration retail banking
application published by Parasoft under the Apache 2.0 licence, run from its
official Docker image. Northline does not include, modify or redistribute it.
See [NOTICE.md](NOTICE.md).

## What is in here

```
  41  requirements, each tagged observed, derived or assumed
  72  test cases, each recording the design technique that produced it
  67  test cases linked to the specific automated test that runs them
 157  automated tests across eight suites
  10  configurable quality gates
   8  defects with evidence and reproduction steps
   6  user acceptance scenarios
  27  documents, most of them generated from a source of truth
```

| Layer | What it catches | Tests |
| --- | --- | --- |
| Smoke | An environment not fit to test at all | 5 |
| API | Broken contracts, wrong status codes, bad validation | 31 |
| Browser | Broken screens, navigation, client-side validation | 37 |
| Database | A screen saying success while the data says otherwise | 16 |
| Reconciliation | Money that does not add up between systems | 18 |
| Accessibility | An interface unusable with assistive technology | 20 |
| Security-adjacent | Data reachable by someone who should not reach it | 11 |
| Certification | A release that should not ship | 19 |

Plus 22 Postman assertions run through Newman, and a JMeter load profile.

## The parts worth looking at

**[Settlement reconciliation](reconciliation/)** generates a settlement file from
the ledger and compares it back, detecting missing records, duplicates, amount
mismatches, account mismatches and unexpected entries. Every break type is
injected deliberately and the engine must find exactly that break **and nothing
else**, because a reconciler reporting six problems when one exists is as
useless as one reporting none. The engine is a pure function over two lists, so
it is tested exhaustively with no environment at all.

**[The certification engine](certification/)** reads the gate thresholds from
[quality-gates.yaml](quality-gates.yaml) and the evidence from real report files,
then returns GO, CONDITIONAL GO or NO-GO. Two rules shape it. Missing evidence
is **not** a pass: a gate with no report records "no evidence" and still blocks,
so deleting a report can never certify a release. And every gate is evaluated
even after one has forced a NO-GO, because a report that stops at the first
problem hides the rest.

**[The ledger checks](tests/database/)** are where the project stops trusting
screens. A confirmation message is not evidence that money moved. These perform
a transfer, re-extract from the source system into PostgreSQL, and assert that
the source fell by exactly the amount and the destination rose by exactly the
same, with money compared as `Decimal` throughout because floating point cannot
represent one cent.

**[Test design](docs/test-design-techniques.md)** applies six formal techniques
to real inputs rather than defining them. The pairwise example was computed, not
asserted: three browsers, two account types and three amount classes give 18
combinations and 21 distinct pairs, reduced to 9 combinations covering all 21.

## Running it

```bash
git clone https://github.com/Priyaj11/northline.git && cd northline
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium firefox webkit
npm install

make env          # start ParaBank and PostgreSQL, provision, check readiness
make smoke        # is this build worth testing at all
make evidence     # run every suite and collect the evidence
make certify      # produce the release decision
```

`make help` lists every target. Anything a pipeline does can be run by hand;
a step that only exists in a workflow file cannot be debugged when it fails.

## Continuous integration

Two pipelines, both green.

**[Pull request](.github/workflows/pull-request.yml)**, under three minutes:
validates every register, fails if the committed documentation differs from what
the generators produce, then runs smoke, API, browser, accessibility and Postman.

**[Nightly](.github/workflows/nightly-regression.yml)**, under four minutes: all
three browsers, database, reconciliation, the full accessibility scan, security,
and every report.

Performance and visual regression are **deliberately excluded**, with reasons in
[docs/ci-cd.md](docs/ci-cd.md). A shared runner's timing is not comparable
between runs, so a performance gate there would fail for reasons unrelated to
the code. Visual baselines are per platform and per browser, and letting a
runner create its own unattended defeats the point of having a baseline.

## Design decisions

Choices with rationale, as distinct from work not done.

**Money is `Decimal` everywhere**, and `NUMERIC(15,2)` in PostgreSQL. Floating
point cannot represent 0.01 exactly, so a ledger stored in floats accumulates
error that looks like a reconciliation break and is not, while hiding the real
one-cent errors that are.

**Documentation is generated from registers.** Requirements, test cases, the
traceability matrix, the defect report and the UAT scenarios all come from YAML
files, and the pipeline fails if the committed output differs from what the
generators produce. Documentation that can drift, does.

**A committed generated file must be deterministic.** This one was learned the
hard way: a generation timestamp in the defect report made the drift check
impossible to satisfy, so the check could never pass. Records that legitimately
change, such as the certification and the accessibility scan, are separate from
views that must not.

**Known defects are marked `xfail(strict=True)`**, so the suite stays green for
new regressions while the defect stays visible. The release gate reads the
defect register, not the test results, so marking a test cannot quietly remove a
defect from the decision.

**Jira is an export target, not the source of truth.** The registers live in the
repository, and [scripts/generate_jira_import.py](scripts/generate_jira_import.py)
produces importable CSV files. A project whose requirements live in a free tier
stops working when the tier changes.

**Selectors are never guessed.** Every page object is written from a document
generated against the running application. Discovery scripts capture the
endpoints, the API response shapes, the page structure and the tables, and each
is regenerated rather than remembered.

## Known limitations

Stated rather than buried.

**Manual accessibility checks have not been performed.**
[docs/accessibility-manual-checklist.md](docs/accessibility-manual-checklist.md)
has a blank result column on purpose. Automated scanning covers roughly a third
of real accessibility barriers, and a checklist filled in without performing the
checks looks like evidence and is not.

**Two acceptance scenarios are designed but not executed.** UAT-05 and UAT-06 in
[docs/uat-scenarios.md](docs/uat-scenarios.md). The other four are covered end to
end by automation, and the document records which is which rather than implying a
manual pass.

**Northline validates the system of record as exposed through the API**, not
ParaBank's raw internal tables. Its database is HyperSQL and reaching it from
Python would require a Java bridge, so the certification data store is fed from
the service layer instead. That mirrors how a real reconciliation engine reads a
core banking extract.

**Performance results describe one laptop.** The load generator, the application
server and the database shared a machine. They are not a capacity measurement,
and [docs/performance-notes.md](docs/performance-notes.md) records how the first
run was green and completely invalid before that was caught.

**One browser test is skipped**, with the measurements that led to it recorded in
the file. Four diagnoses were wrong before the cause was measured rather than
reasoned about, and a skip carrying real evidence beats a workaround that turns
green while proving nothing.

## Documentation

| Document | What it holds |
| --- | --- |
| [Release certification](docs/release-certification.md) | The decision, gate by gate, with evidence sources |
| [Test summary report](docs/test-summary-report.md) | Execution, defects, coverage, the decision |
| [Test strategy](docs/test-strategy.md) | Approach, levels, risks, entry and exit criteria |
| [Test plan](docs/test-plan.md) | What runs, when, and how it is judged |
| [Test design techniques](docs/test-design-techniques.md) | Six techniques applied to real inputs |
| [Traceability matrix](docs/requirements-traceability-matrix.md) | Requirement to test case to automation to defect |
| [Defect report](docs/defect-report.md) | The register with metrics |
| [Quality gates](docs/quality-gates.md) | The thresholds and why they are set there |
| [Accessibility report](docs/accessibility-report.md) | axe-core findings, and what a scan cannot tell you |
| [Security test plan](docs/security-test-plan.md) | Scope, results by layer, and what was not tested |
| [Performance notes](docs/performance-notes.md) | Results, and the invalid first run |
| [CI and CD](docs/ci-cd.md) | Both pipelines and what is excluded |
| [System under test](docs/sut-parabank.md) | ParaBank's quirks, discovered rather than assumed |

## Built by

Priya Jaffarali — [github.com/Priyaj11](https://github.com/Priyaj11)
