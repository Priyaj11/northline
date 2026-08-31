# Continuous integration and delivery

Two pipelines, in .github/workflows/.

## Pull request pipeline

Runs on every pull request and on every push to main.

    validate-documentation    the four generators, then a check that the
                              committed documentation matches what they produce
    test                      smoke, API, Chromium UI, accessibility, Postman

Two jobs rather than one, because the generators need no environment and finish
in under a minute. A register that has drifted fails immediately instead of
after a browser install and a container start.

The documentation check is the part worth explaining. Each generator exits
non-zero when a register is inconsistent: an unknown requirement, a defect whose
writeup is missing, a requirement with no test case. After they run, the
pipeline compares the regenerated files against the committed ones and fails if
they differ. Editing a register without running `make docs` therefore cannot
merge.

Target: under ten minutes. A pull request check that takes twenty minutes gets
ignored or bypassed, and a check people bypass is not a check.

## Nightly pipeline

Runs at 07:00 UTC and on demand.

    every browser, database, reconciliation, full accessibility scan, security,
    every generated report, and the Jira export

Buys thoroughness with time nobody is waiting on.

## What is deliberately excluded, and why

### Performance

JMeter is not in either pipeline.

A shared runner's timing is not comparable between runs. The processor is
shared with other tenants, the memory allocation varies, and a run that
reported a 95th percentile of 200 milliseconds one night and 900 the next would
say nothing about the application. Worse, it would fail a threshold gate for a
reason that has nothing to do with the code.

Performance runs locally, with the environment recorded alongside the numbers.
See docs/performance-notes.md, which also documents the first run being green
and invalid.

### Visual regression

Excluded from both pipelines, using the `visual` marker:

    pytest -m "ui and not visual"

Baselines are stored per platform AND per browser, at
tests/ui/baselines/<platform>/<browser>/, because font rendering, form control
styling and sub-pixel antialiasing all differ between operating systems. This
repository holds macOS baselines only, so a Linux runner has nothing valid to
compare against.

Two alternatives were considered and rejected.

Letting the runner create Linux baselines automatically would mean accepting
whatever the first run produced, with nobody looking at it. That is precisely
the failure mode the baseline mechanism exists to prevent, and it happened
accidentally during this phase: a baseline directory move failed silently, the
next run created replacements unattended, and the run afterwards passed against
images nobody had reviewed. They turned out to be identical to the originals,
which was luck rather than process.

Running the visual suite in a container matching the developer's platform would
work, and is what a team with more than one contributor should do. It is
recorded as a future improvement rather than built, because with one contributor
on one machine it would add a container to maintain and catch nothing.

## Failure artifacts

Both pipelines upload with `if: always()`, because the traces, screenshots and
reports you need are the ones from a failed run. Both also dump the last of the
application log on failure, since a failure caused by the environment looks
identical to a failure caused by the code until you read it.

## Test data between steps

The nightly pipeline resets the application data before the database and
reconciliation suites. Those suites assert on absolute values, and the UI and
API suites that run before them move money. Without the reset the results would
depend on the order the steps happened to run in.

## Known risks in these pipelines

Written before the first run, and updated afterwards with what actually
happened.

    ParaBank start time        one to three minutes locally, plus a cold image
                               pull on a runner. The readiness check waits, but
                               the job timeout has to allow for it.

    WebKit system libraries    installed with --with-deps, which is why that
                               flag is there rather than a bare install.

    Runner memory              the application server, PostgreSQL, a browser and
                               the test process all on one runner.

## Local equivalents

Every pipeline step has a Makefile target that does the same thing:

    make env        start, provision and check the environment
    make docs       run all four generators
    make smoke      the smoke suite
    make db         the database suite
    make recon      the reconciliation suite
    make a11y-test  the accessibility suite
    make sec        the security suite
    make ui         the browser suite
    make perf       the performance profiles, local only

Anything a pipeline does should be runnable by hand. A step that only exists in
a workflow file cannot be debugged when it fails.

## First pipeline run: what actually failed

Recorded 2026-08-31, replacing what this section previously guessed at.

The first run failed on the documentation drift check, and the failure was real:

    docs/defect-report.md | 2 +-
    1 file changed, 1 insertion(+), 1 deletion(-)

One line, and it was a timestamp. scripts/generate_defect_report.py wrote the
current time into the markdown, so regenerating always produced a different
file. The check could never have passed, no matter what anyone committed.

### The rule that follows

A generated artefact that is committed must be DETERMINISTIC: the same inputs
produce the same bytes.

A timestamp inside one guarantees a difference on every run. That turns a drift
check into permanent noise, and a check that is always red gets bypassed, which
is worse than not having it.

The timestamp added nothing anyway. Git records when a file was committed, and
the generation time is still recorded in reports/defects.json, which the
certification engine reads and which is not committed.

### What this cost, and what it was worth

The check failed for the right reason on its very first execution: the
committed documentation genuinely did not match what the generators produced.
It just could not have matched. Finding that on the first run rather than after
weeks of people ignoring a red check is the argument for pushing early rather
than at the end.

### Note on the accessibility report

docs/accessibility-report.md also carries a generation date and is committed. It
is NOT subject to the drift check, because its content depends on a live scan
against a running application rather than on a register, so regenerating it
without the environment would produce a different document for legitimate
reasons. It is regenerated by the nightly pipeline, which does not compare it
against the committed copy.
