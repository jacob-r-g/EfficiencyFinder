# EfficiencyFinder

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://img.shields.io/github/actions/workflow/status/jacob-r-g/EfficiencyFinder/ci.yml?branch=main&label=CI)](https://github.com/jacob-r-g/EfficiencyFinder/actions/workflows/ci.yml)

Web app for CRISPR editing-efficiency analysis from nanopore amplicon FASTQ. A FastAPI backend runs the shared `core/` engine; a React UI handles uploads and results. Analysis is offline once the stack is running.

Per sample it reports:

- Read classification to amplicon (assigned vs unassigned)
- WT vs edited at each guide cut (Cas9: 3 bp up + 3 bp down; Cas12: spacer 16–23)
- Indel size and in-frame vs frameshift
- Distinct alleles (for chimerism)
- Paired-guide excision (both cuts at once, intervening fragment dropped)

Supports **SpCas9** and **Cas12a**.

## Quick start (local)

API on port 8000, Vite on 5173:

```bash
python3 -m pip install -r web/backend/requirements.txt -r requirements.txt
PYTHONPATH=. python3 -m uvicorn web.backend.app:app --reload --port 8000
```

```bash
cd web/frontend
npm install
npm run dev
```

FASTQ uploads are chunked (8 MB) so large files can pass reverse-proxy size limits.

### Docker

```bash
docker compose up --build
# → http://localhost:4322
```

Or build and run the image from the repo root:

```bash
docker build -t efficiencyfinder-webapp .
docker run --rm -p 4322:4322 -v ef-data:/data efficiencyfinder-webapp
```

Bump the repo-root `VERSION` file before a release so the live UI header / `/health` match what you deployed.

> **Security:** the web API has no authentication. Only expose it on trusted networks, or put auth in front (VPN, reverse-proxy login, Cloudflare Access, etc.). See [SECURITY.md](SECURITY.md).

### Optional remote deploy script

`deploy.sh` builds a linux/amd64 image, copies it over SSH, and restarts a Docker container (defaults tuned for Unraid-style hosts). Copy `deploy.config.example` → `.deploy.config`, set host/user/path, then run `./deploy.sh`. Use `--skip-build` to reuse a local image.

## Inputs

**FASTQ:** standard 4-line files, optionally gzip-compressed (`.fastq.gz` / `.fq.gz`). Quality scores are ignored. Select many files at once for a batch.

**FASTA:** one combined amplicon + guide file.

```
>Line10
ACGT...full WT amplicon...

>Line10_G61
CCACTTCGGCTAGCCGAATGGGA
```

- Amplicon headers must **not** contain `_G`. Sequence is the full WT amplicon.
- Guide headers **must** contain `_G`, and the text before the first `_G` must match the amplicon header exactly (including case and spaces).
- Guide sequence must be an exact substring of that amplicon on either strand:
  - **SpCas9:** protospacer + NGG PAM
  - **Cas12a:** first 4 bp of the guide entry are the PAM (as written, any sequence) + spacer
- Choose the matching nuclease in the UI (default SpCas9). The WT window is cut-local: Cas9 = 3 bp up + 3 bp down of the blunt cut; Cas12 = spacer positions 16–23.
- An amplicon can have 0, 1, or several guides. Empty guide sequences are skipped.

Tiny synthetic demo files are in [`examples/`](examples/).

## Results

Tabs, all sortable/filterable and exportable to CSV:

| Tab | What it shows |
|---|---|
| **Assignment** | Per-sample assigned vs unassigned reads; per-amplicon counts; download unassigned FASTQ |
| **Efficiency** | Per-guide cut-local WT vs edited % (Cas9: 6 bp at cut; Cas12: spacer 16–23; distal spacer noise ignored; failed flanks = inconclusive). Select a row to inspect example reads. |
| **Indel & Frame** | Net indel size at the guide window, in-frame vs frameshift. Substitutions are WT here. Per-guide histogram. |
| **Alleles** | Distinct edit outcomes per sample (always amplicon 5′→3′; deletions as N vs WT), plus alleles shared across the batch |
| **Paired excision** | For amplicons with 2+ guides: reads with failed local flanks at every guide, with confirmed outer-flank dropout size |

Advanced settings (collapsed by default) expose the analysis thresholds. The UI also includes an on-site guide to columns and parameters.

## Tests

```bash
python3 -m pip install -r requirements.txt -r web/backend/requirements.txt
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, layout, and PR expectations. Please read the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
