# EfficiencyFinder

Desktop app for CRISPR editing efficiency from nanopore amplicon FASTQ. Fully offline: pick a reference FASTA and one or more FASTQ files, then run.

It reports, per sample:

- Read classification to amplicon (assigned vs unassigned)
- WT vs edited at each Cas9 cut (3 bp up + 3 bp down of the cut must match for WT)
- Indel size and in-frame vs frameshift
- Distinct alleles (for chimerism)
- Paired-guide excision (both cuts at once, intervening fragment dropped)

## Run

**macOS:** unzip the folder, put the whole **EfficiencyFinder** folder in Applications, then double-click **`Setup EfficiencyFinder.command`** once (see `START HERE.txt`).

After setup, open **`EfficiencyFinder.app`** (drag it to the Dock if you like). Keep the whole folder together — do not move only the `.app` out of the folder.

Do not send the `.venv` folder (it is large and rebuilt automatically).

**From a terminal (optional):**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Python 3.10+, with PySide6, numpy, and matplotlib.

## Web app (home server)

The same analysis runs in the browser via a FastAPI backend. FASTQ is uploaded in 8 MB chunks so it can pass Cloudflare's request-size limit.

**Local development** (API on port 8000, Vite on 5173):

```bash
python3 -m pip install -r web/backend/requirements.txt
PYTHONPATH=. python3 -m uvicorn web.backend.app:app --reload --port 8000
```

```bash
cd web/frontend
npm install
npm run dev
```

**Deploy to Unraid** (port 4322):

```bash
cp deploy.config.example .deploy.config   # once; set host / path
./deploy.sh                               # enter Unraid SSH password when prompted
```

Bump the repo-root `VERSION` file before a deploy so you can confirm the live site (header `v…` or `/health`). Use `./deploy.sh --skip-build` to reuse an image you already built locally. Cloudflare Tunnel should point a public hostname at `http://localhost:4322` on the Unraid host.

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
- Guide sequence is the protospacer+PAM and must be an exact substring of that amplicon on either strand.
- An amplicon can have 0, 1, or several guides. Empty guide sequences are skipped.

Example files are in `sample files/`.

## Results

Tabs, all sortable/filterable and exportable to CSV:

| Tab | What it shows |
|---|---|
| **Assignment** | Per-sample assigned vs unassigned reads; per-amplicon counts; download unassigned FASTQ |
| **Efficiency** | Per-guide cut-local WT vs edited % (WT = exact 6 bp at the Cas9 cut; distal spacer noise ignored; failed flanks = inconclusive) |
| **Indel & Frame** | Net indel size at the guide window, in-frame vs frameshift. Substitutions are WT here. Per-guide histogram. |
| **Alleles** | Distinct edit outcomes per sample, plus alleles shared across the batch |
| **Paired excision** | For amplicons with 2+ guides: reads with failed local flanks at every guide, with confirmed outer-flank dropout size |

Advanced settings (collapsed by default) expose the analysis thresholds.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```
