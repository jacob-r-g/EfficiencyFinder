# Security Policy

## Supported versions

Security fixes are applied to the latest release on `main` (see `VERSION`).

## Reporting a vulnerability

Please open a [private security advisory](https://github.com/jacob-r-g/EfficiencyFinder/security/advisories/new) on GitHub, or email the maintainer via the address listed on their GitHub profile. Do not file a public issue for exploitable vulnerabilities.

## Deployment notes

The web API has **no authentication**. Anyone who can reach the server can upload FASTQ and start analyses. That is intentional for trusted lab networks; it is **not** safe to expose the container to the public internet without an auth layer (reverse proxy, VPN, Cloudflare Access, etc.).

Uploads and results are stored on disk under `EFFICIENCYFINDER_DATA` (default `/data` in Docker) and expire after about one hour (`UPLOAD_TTL_S` / `RESULT_TTL_S` in `web/backend/store.py`). Jobs are serialized so only one analysis runs at a time.

## Historical sample data

Early commits briefly included real sequencing files under `sample files/`. Those paths are gitignored and are not in the current tree. If that data must not be public, rewrite history (for example with [`git filter-repo`](https://github.com/newren/git-filter-repo)) to purge `sample files/` **before** making the repository public, then force-push and rotate any credentials that ever lived in the repo.

Synthetic demo inputs live in `examples/` and are safe to share.
