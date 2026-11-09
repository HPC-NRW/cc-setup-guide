# Guide regression tests

Tests consume `--source` from the current working tree, including untracked files.
Use a private, disposable `--work` outside any existing installation. No test may
point at a production installation. There are no credentials, databases or large
upstream checkouts in this directory. All integration services bind loopback.

Install `requirements-test.txt` in a virtual environment. Configure `TMPDIR`,
`XDG_CACHE_HOME`, `PIP_CACHE_DIR`, `GOCACHE`, `GOMODCACHE` and
`PLAYWRIGHT_BROWSERS_PATH` to your disposable workspace when space is constrained.
Integration exports and work directories contain synthetic secrets: keep them
private and do not upload them as public CI artifacts.

## Fast checks

```bash
python tests/test_docs.py --source . --work "$TEST_WORK/docs"
python tests/test_subcluster.py --source . --work "$TEST_WORK/topology"
python tests/test_hardware.py --source . --work "$TEST_WORK/hardware"
python tests/test_metrics.py --source . --work "$TEST_WORK/metrics"
python tests/test_configure_collector.py --source . --work "$TEST_WORK/configure"
python tests/test_update_userconfig.py --source . --work "$TEST_WORK/userconfig"
python tests/installer_unit.py --source . --work "$TEST_WORK/installer-unit"
```

`test_update_userconfig.py` needs Perl with `DBI` and `DBD::SQLite`
(`libdbi-perl` and `libdbd-sqlite3-perl` on Ubuntu/Debian). It uses disposable
SQLite databases to check all preference-key mappings, unchanged values,
cluster/subcluster suffixes, preview mode, repeated runs, schema checks,
existing-key conflicts and transaction rollback.

`test_docs.py --browser` checks language switches, rendering and search under the
real `/cc-setup-guide/` prefix. It also runs the bundled axe-core 4.14.0 against
every generated page in light and dark mode, checks alternative text, language
and heading structure, 320 CSS-pixel reflow, keyboard access to scrolling content,
skip links and expandable configuration examples. It also exercises mobile
navigation and search while open, including modal focus, Material's arrow-key
result selection, Enter activation and Escape return. Every indexed section must
have its document parent, and actual result links must resolve. The browser blocks external
requests. Results, including rules needing manual review, are saved in
`accessibility-results.json`. These regressions complement manual image
descriptions, screen-reader and keyboard review; they do not certify WCAG
conformance. The unmodified test-only engine and its MPL-2.0 license are in
`tests/vendor/axe-core/`, outside the published documentation.

It needs Playwright Chromium, or `--browser-executable /path/to/chromium`.
The topology helper requires Perl with
`JSON::PP`; tests substitute controlled programs and never touch MSRs or GPUs.
For exact LIKWID events and actual converter output add the pinned source trees:

```bash
python tests/test_hardware.py --source . --work "$TEST_WORK/hardware-full" \
  --likwid-source "$LIKWID_SOURCE" --collector-source "$COLLECTOR_SOURCE"
```

`test_metrics.py` validates every example JSON with duplicate-key rejection and
checks both complete cluster profiles against the unmodified upstream schemas,
without exceptions. The cc-lib 2.9.1 and 2.12.0 cluster/unit schemas are identical;
their hashes and the expected 24 RUB metric units are recorded in
`schema-contract.json`. Unsupported percent, counter, and named-rate metrics
must be absent from the backend profile and dropped by the actual router.

## Actual router and collector

Build the small router driver with Go 1.25 or newer and `GOTOOLCHAIN=local`.
It executes the pinned collector's cc-lib 2.12.0 message processor:

```bash
(cd tests/router && GOTOOLCHAIN=local go build -mod=readonly -o "$TEST_WORK/router" .)
python tests/test_metrics.py --source . --work "$TEST_WORK/router-cases" \
  --router-binary "$TEST_WORK/router"
```

This checks known numeric transformations, both device tag spellings, rejection
of other disks, every intermediate tutorial whitelist and the complete RUB
router. `test_hardware.py` checks the published `collectors.json` Zen4 profile:
clock, IPC, power, combined FLOPS, and every read/write memory channel with
independent inputs. It also checks the documented DE/EN Zen4 intermediate
metrics and their global sum, the SPR byte/time conversion, and all RUB
topologies. Optional upstream sources verify Zen4 event names and compare the
three complete converter outputs with both language versions. These are
fixtures, not hardware qualification; removed historical CPU/GPU/Zen5 profiles
are not test inputs.

The Linux memstat conversion also has a real collector regression with a
read-only synthetic `/proc/meminfo` and the current RUB router:

```bash
python tests/test_memstat.py --source . --work "$TEST_WORK/memstat" \
  --collector "$COLLECTOR_SOURCE/cc-metric-collector"
```

With MemTotal2097152 and MemFree1048576 reported as Linux `kB`, it requires
exactly **1.073741824 GB** after relabelling KiB and applying the router's unit
conversion. It executes memstat itself; NUMA and hardware collectors are off,
`/sys` is empty, and the network namespace has no external access.

Build collector v0.8.4 using the exact public collector setup instructions and
`versions.json`. Then create disposable installation exports as described in
[INSTALLER.md](INSTALLER.md). The lifecycle test refuses inputs without the
installer harness's `.guide-test-fixture` marker:

```bash
python tests/test_metrics_runtime.py --source . --work "$TEST_WORK/lifecycle153" \
  --installation "$INSTALLER_WORK/export/backend153" \
  --collector "$COLLECTOR_SOURCE/cc-metric-collector"
python tests/test_metrics_runtime.py --source . --work "$TEST_WORK/lifecycle154" \
  --installation "$INSTALLER_WORK/export/backend154" \
  --collector "$COLLECTOR_SOURCE/cc-metric-collector"
```

Linux bubblewrap provides only an artificial hostname and isolated process
namespace. The test copies the actual fresh installation, preserves its keys,
JWT and database, and uses current tutorial/minimal files and the documented
configuration helper. Explicit test changes are loopback, 2-second sampling,
1-second archive worker, a small store memory limit and a synthetic control
metric. The stdout sink is an independent observation of real loadavg samples.
It checks all values in order and their count, absolute checkpoint timestamps,
restart, actual archive status 3, and a separate restore via the guide's
inventory-based offline backup helper. JSON checkpoints permit only the
documented one-decimal rounding tolerance of 0.051. Job API arrays have no
per-series start timestamp; absolute timestamps are verified in the checkpoints.
The short quickstart job proves first-metric ingress; the longer tutorial job
tests archival. Every launched process is stopped in cleanup.

## Backend unit contract

```bash
python tests/test_backend_units.py --source . --work "$TEST_WORK/backend-units" \
  --installation "$INSTALLER_WORK/export/backend153" \
  --router-binary "$TEST_WORK/router" \
  --browser --browser-executable /path/to/chromium
```

The actual backend must start with both complete cluster profiles under
`main.validate: true`. Real router values, native resource scopes, archived
series, returned units, and browser display are then checked with the unchanged
upstream runtime default. Known Linux `/proc/meminfo` values are corrected from
their `kB` label to KiB before scaling, using the targeted router rule.

A separate regression records an upstream limitation of the global validation
switch in backend 1.5.3 and 1.5.4: job-archive validation can reject metadata
written by the backend itself because required statistic metrics are absent or
nullable output fields fail the archive schema. This does not exempt the cluster
configuration from schema validation. No product or schema patches are applied.

## Energy and footprint

```bash
python tests/test_energy.py --source . --work "$TEST_WORK/energy153" \
  --installation "$INSTALLER_WORK/export/backend153"
```

This runs the current, identical DE/EN power example through backend1.5.3:
spatial `aggregation: sum`, temporal `footprint: avg`, and `energy: power`.
Two artificial nodes with two synthetic GPUs each receive 30 values of 1500W
per GPU at 2-second intervals. It checks all four native archive series, both
3000W node aggregates, the 60-second job, archive status3, the persisted
footprint and **0.10kWh** total energy. The test uses the raw installer JWT and
stops its backend. This is a numeric API/archive contract, not a GPU or power
measurement. Work data contains private fixture credentials.

## Operations and migration

[OPERATIONS.md](OPERATIONS.md) documents the bounded adapter, older-sync
compatibility, LDAP/proxy, and migration tests, including required immutable
upstream inputs. They use unmodified upstream sources and submit payloads to
the actual backend. The older sync check records its incompatibility rather
than applying a guide patch. Migration and restore use artificial jobs and
the documented offline inventory. Fixtures do not establish real Slurm,
LDAP-directory, or hardware compatibility.

The PR workflow runs the inexpensive documentation and fixture checks with
read-only repository permissions. It has no deployment job or production access.
Real installer, collector and migration tests are deliberately explicit local
integration commands with their own disposable environments.
