# EfficiencyFinder

Desktop app for CRISPR editing efficiency from nanopore amplicon FASTQ. Fully offline: pick a reference FASTA and one or more FASTQ files, then run.

It reports, per sample:

- Read classification to amplicon
- WT vs edited (insertions, small/large deletions, substitutions)
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

**Deploy to Unraid** (port 4322, same pattern as the g-force webapp): copy `deploy.config.example` to `.deploy.config`, then `./deploy.sh`. Add a Cloudflare Tunnel public hostname pointing at `http://localhost:4322`.

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

Four tabs, all sortable/filterable and exportable to CSV:

| Tab | What it shows |
|---|---|
| **Efficiency** | Per-guide WT vs edited counts and % (substitutions count as edited) |
| **Indel & Frame** | Net indel size, in-frame vs frameshift. Substitutions are WT here. PNG histogram export. |
| **Alleles** | Distinct edit outcomes per sample, plus alleles shared across the batch |
| **Paired excision** | For amplicons with 2+ guides: reads that are large-deleted at every cut site at once, with confirmed dropout size |

Advanced settings (collapsed by default) expose the analysis thresholds.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```
