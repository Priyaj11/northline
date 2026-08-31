# Performance testing notes

Written alongside the generated report in reports/performance-report.md, which
holds the numbers. This holds what the numbers mean and what went wrong getting
them.

## The first run was invalid, and it looked fine

The first set of profiles reported these results, all passing:

    threads requested   p95      throughput/s
    10                  7 ms     80.0
    25                  8 ms     76.9
    50                  8 ms     75.9

Every threshold passed. Nothing was obviously wrong. The only signal was that
the numbers did not change as load increased. Five times the threads produced
identical response times and slightly LOWER throughput.

A result that ignores its own input variable is not measuring what it claims to
measure.

The cause was in the profile, not the application. Each thread had only 15
requests to make, at about 4 milliseconds each, so a thread finished in well
under a second. The ramp-up was calculated as users divided by five, so at 50
threads it spread starts over 10 seconds. Threads were finishing faster than
the ramp could start them.

Checking JMeter's allThreads field confirmed it. Peak concurrency actually
achieved:

    threads requested   peak concurrency observed
    10                  1
    25                  1
    50                  2

The test never applied concurrent load at all. It measured a trickle of
sequential requests.

## Why this matters more than the numbers

A load test that never achieves its stated concurrency is worse than no load
test, because it produces confident numbers that get quoted. "We tested at 50
concurrent users" would have been false, and nobody reading the report could
have known.

The fix was more work per thread and a shorter, fixed ramp: 40 loops instead of
5, and a flat 5 second ramp instead of one that grew with the thread count.

## Concurrency is still below the requested count

After the fix:

    threads requested   peak concurrency observed
    10                  3
    25                  10
    50                  40

Better, and enough to produce a genuine load response, but still short of the
requested numbers for the same underlying reason. The report states both
figures side by side rather than only the requested one. Reporting 50 when the
peak was 40 is a small overstatement, and small overstatements are how a habit
starts.

## The finding in the corrected data

    peak concurrency   p50     p95      throughput/s
    3                  4 ms    13 ms    243
    10                 7 ms    27 ms    548
    40                 19 ms   191 ms   546

Throughput stopped growing between the second and third profiles, 548 then 546,
while the 95th percentile went from 27 milliseconds to 191.

That is the shape of saturation. Past the point where a system can process
faster, additional load turns into queueing rather than throughput. Requests do
not get served more quickly, they wait longer. Something in the chain reached
its limit at roughly 550 requests per second under these conditions.

WHAT saturated is not established. The load generator, the application server,
the database and the operating system were all on one machine with 8 GB of
memory, so the bottleneck could have been any of them, including JMeter itself.
Identifying it would need resource monitoring on each component, which was not
performed. The plateau is reported as observed; its cause is not claimed.

## Environment

    One laptop, Apple Silicon, 8 GB memory
    Load generator, application server and database all on the same machine
    ParaBank and PostgreSQL in Docker
    JMeter in non-graphical mode

JMeter's own documentation advises against running load through its graphical
interface, because the interface collects every sample in memory and becomes
the bottleneck. All runs used non-graphical mode with the -n flag.

## What these results are not

They are not a capacity measurement. No conclusion about how many customers the
application could serve should be drawn from them, because the load generator
competed for the same processor and memory as the system it was measuring.

In a real bank the load generator sits on separate infrastructure, the
thresholds come from service level agreements rather than a QA engineer's
judgement, and the environment is sized to resemble production.

What these results do demonstrate is a load profile applied and verified,
thresholds held in configuration rather than code, results checked against them
mechanically, and a saturation point identified from the data.
