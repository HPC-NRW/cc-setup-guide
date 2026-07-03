## ClusterCockpit Setup Guide

### Installation of Documentation

This repository contains the documentation for installing and configuring ClusterCockpit on an HPC system. Follow the instructions below to clone the repository and serve the documentation website locally using MkDocs.

The guide is kept up to date on a best-effort basis. For problems, corrections, or change requests, please open an issue at <https://github.com/hpc-nrw/cc-setup-guide/issues>.

#### Prerequisites

Make sure the following software is available:

- Git
- Python 3.8 or higher (3.10/3.11 recommended)
- Pip (and optionally `venv`)

**Python packages (installed via `requirements.txt`):**
- `mkdocs` (static site generator)
- `mkdocs-material` (theme)
- `mkdocs-static-i18n` (multi-language support)
- `mkdocs-minify-plugin` (optional: smaller HTML)
- `mkdocs-redirects` (optional: maintain old URLs)

#### Installation on Ubuntu/Debian

```bash
# install git
sudo apt update && sudo apt install -y git

# install python and pip
sudo apt install -y python3 python3-pip python3-venv

# verify installation
python3 --version
pip3 --version
````

#### Clone & Setup

```bash
git clone https://github.com/hpc-nrw/cc-setup-guide.git
cd cc-setup-guide

# (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

#### Serve Locally

```bash
mkdocs serve
```

Open the printed URL (typically [http://127.0.0.1:8000](http://127.0.0.1:8000)).
The site is **multi-language**: English is the default; use the language selector in the UI to switch to German.

#### Build Static Site

```bash
mkdocs build
```

This will generate a production-ready site in the `site/` directory.

### Troubleshooting

* If `mkdocs serve` fails, ensure all dependencies from `requirements.txt` are installed correctly (`pip list`).
* Clear your browser cache if CSS or theme changes aren’t visible after rebuilds.
