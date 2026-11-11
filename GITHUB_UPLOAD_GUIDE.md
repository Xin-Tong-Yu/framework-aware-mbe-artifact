# Browser-only GitHub upload guide

This **results-free repository bundle** was organized for browser upload: it contains fewer than 100 files in total, and each committed file is less than 25 MiB. It contains source code, two runnable experiment packages, and the 13 graph inputs as archive pieces; it does not contain any machine-generated results or historic V1-V60 trial archives.

1. Confirm third-party code/data redistribution rights using `SOURCE_ATTRIBUTION.md` and `RELEASE_CHECKLIST.md`.
2. Sign in to GitHub in a browser, and open the intended public repository.
3. Click **Add file → Upload files** (or **uploading an existing file** for an empty repository).
4. In a **freshly extracted copy of this bundle**, select the contents of the repository folder and drag them to the upload page. Keep the directory structure intact. Do not drag a parent directory, a `.git/` folder, the uncompressed `data_clean/` folder, or generated `outputs/`.
5. The prepared package contains fewer than 100 files. If the browser still refuses a large batch, upload `README.md` and other root documentation first, then `scripts/`, `runners/`, `src/`, and `data/` in subsequent batches. **Commit changes** after each batch.
6. Open the published repository from a logged-out browser session to confirm public access. Review the rendered README and make sure the six `data/parts/*.part` files appear.
7. Only after confirming that the repository covers all results required for the intended paper submission, provide its URL to the conference. This version is a verified-core subset and does **not** yet contain every manuscript ablation.

GitHub browser uploads are authenticated using your GitHub web session; no terminal Git password or personal access token is needed. Do not include access tokens, passwords, unreviewed internal logs, or local `.git` metadata.

## Additional paper ablation source bundle

The approximately 400 KB `MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip` has already been uploaded to `src/paper_ablations/`. Do not upload it again. It is not precomputed results. After cloning, test with `python3 scripts/setup_paper_ablations.py --check-only` followed by `python3 scripts/setup_paper_ablations.py`. The checkout must contain the complete six-part graph archive as well. The directories in `src/paper_ablations/` describe each campaign; the bundled code is extracted to an ignored build area rather than scattered across the repository.
