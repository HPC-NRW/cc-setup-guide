## ClusterCockpit Setup Guide

### Installation of Documentation

This repository contains the documentation for installing and configuring ClusterCockpit on an HPC system. MkDocs builds the German and English guides and serves a local preview.

The guide is maintained as time allows. Reports of problems, corrections, and suggestions are welcome in the [issue tracker](https://github.com/hpc-nrw/cc-setup-guide/issues).

The [introduction](docs/index.en.md) links the complete installation path. Separate sections cover optional metrics, operation and maintenance, reference configurations, and troubleshooting. The prose uses concrete subjects and active verbs without directly addressing the reader; German instructions use the infinitive where a short action is clearer.

Published examples use the pinned upstream releases without product patches. Both cluster profiles are checked against the original schemas without exceptions; metrics whose units cannot be represented are excluded from the runnable examples.

#### Prerequisites

The documentation build requires:

- Git
- Python 3.9 or higher (CI uses 3.12)
- Pip and `venv`

**Python packages (installed via `requirements.txt`):**
- `mkdocs` (static site generator)
- `mkdocs-material` (theme)
- `mkdocs-static-i18n` (multi-language support)
- `mkdocs-minify-plugin` (required by the configuration: smaller HTML)
- `mkdocs-redirects` (required by the configuration: URL redirects)

#### Installation on Ubuntu/Debian

```bash
# install git
sudo apt update && sudo apt install -y git

# install python and pip
sudo apt install -y python3 python3-pip python3-venv

# verify installation
python3 --version
pip3 --version
```

#### Clone & Setup

```bash
git clone https://github.com/hpc-nrw/cc-setup-guide.git
cd cc-setup-guide

# Isolate the documentation dependencies
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

#### Serve Locally

```bash
mkdocs serve
```

The preview is available at the printed URL, typically [http://127.0.0.1:8000](http://127.0.0.1:8000).
English is the default language. The language selector switches between English and German.

#### Build Static Site

```bash
mkdocs build --strict
```

This will generate a production-ready site in the `site/` directory.

### Troubleshooting

* Missing dependencies can prevent `mkdocs serve` from starting. `pip list` shows the installed packages for comparison with `requirements.txt`.
* A cached stylesheet can hide CSS or theme changes after a rebuild. Clearing the browser cache reloads the current files.

### Regression checks

The supported component versions and immutable source references are recorded in
[`versions.json`](versions.json). Internal author notes live in `maintainer-notes/`
and are not part of the generated website. The documentation requirements pin direct build dependencies;
transitive resolution also depends on the Python version.

Tests read the current working tree, including unstaged and untracked snippets.
They need an empty or dedicated work directory outside any existing installation:

```bash
pip install -r requirements-test.txt
python3 tests/test_docs.py --source . --work /tmp/cc-guide-tests
python3 tests/test_hardware.py --source . --work /tmp/cc-guide-tests
python3 tests/test_subcluster.py --source . --work /tmp/cc-guide-tests
```

The [test overview](tests/README.md) covers router, backend, lifecycle, and
operations integration checks. The [installer tests](tests/INSTALLER.md) create
the disposable installation fixtures needed for these checks.

The topology test needs Perl and `JSON::PP` (`libjson-pp-perl` on Debian/Ubuntu,
`perl-JSON-PP` on AlmaLinux). It supplies controlled LIKWID processes and does not
run hardware benchmarks. The arithmetic test can additionally verify upstream
LIKWID events with `--likwid-source /path/to/likwid-v5.5.1`. The additional option
`--collector-source /path/to/cc-metric-collector` runs the pinned converter
and compares its output with the complete DE/EN examples.

For the real `/cc-setup-guide/` prefix, language switches, rendering and both
search languages, the browser checks can use an existing Chromium/Chrome binary:

```bash
python3 tests/test_docs.py --source . --work /tmp/cc-guide-tests \
  --browser --browser-executable /path/to/chromium
```

Playwright's Chromium is another option when installed in the local test environment;
in that case `--browser-executable` is unnecessary. Browser tests bind only a loopback port and block
external browser requests. A passing documentation or fixture test does not imply
working Slurm, PMU/GPU hardware, systemd deployment or production security policy.
