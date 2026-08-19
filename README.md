# EfficiencyFinder

Desktop app for CRISPR editing efficiency from nanopore amplicon FASTQ. Fully offline: pick a reference FASTA and one or more FASTQ files, then run.

It reports, per sample:

- Read classification to amplicon
- WT vs edited (insertions, small/large deletions, substitutions)
- Indel size and in-frame vs frameshift
- Distinct alleles (for chimerism)
- Paired-guide excision (both cuts at once, intervening fragment dropped)

## Run

**macOS:** unzip the folder, then double-click **`Setup EfficiencyFinder.command`** (see `START HERE.txt`).

macOS may ask if you are sure — click **Open**. First-time setup downloads libraries (2–5 minutes, internet required). The app opens from the same Terminal window — leave that window open (you can minimize it). **Always use the Setup command to open the app**; do not rely on double-clicking `EfficiencyFinder.app` alone.

Keep the whole folder together (do not move only the `.app` out). Do not send the `.venv` folder (it is large and rebuilt automatically).

**From a terminal (optional):**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Python 3.10+, with PySide6, numpy, and matplotlib.

## Inputs

**FASTQ:** standard 4-line files. Quality scores are ignored. Select many files at once for a batch.

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
