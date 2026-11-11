# Manuscript-to-artifact experiment coverage

This file maps the **experiment families** in the manuscript to executable
material in this repository. The repository intentionally has **no archived
benchmark-result CSVs**: scripts generate new outputs locally. Code availability
is not a claim that a reviewer will reproduce identical timings on other hardware.

| Manuscript experiment | Available executable material | Status |
|---|---|---|
| Thirteen cleaned-graph statistics | `data/`, `scripts/prepare_data.py`, `scripts/verify_artifact.py` | All six original archive parts are now present and Git object hashes match; fresh-clone restore test still recommended |
| MBET/MBETM versus Single ST-noCR/ST+CR | `runners/MBE_FAIR_MBET_2024.zip`, `src/fair_mbet/` | Reproduction entry point available (four modes, five repeats) |
| Single Candidate Tree map/inline/cursor/pre-fork | Original campaign code present in `src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip` | **Source uploaded; clean-clone execution and manuscript-table matching pending** |
| Single Result Tree layout and CR factorial ablation | Original campaign code present in `src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip` | **Source uploaded; clean-clone execution and manuscript-table matching pending** |
| Double Vector/Compact state factorial ablation | `src/paper_ablations/` source bundle and `scripts/run_paper_ablations.sh double-2x2` | **Source uploaded; clean-clone execution and manuscript-table matching pending** |
| Incremental Single/Double ST, ET, ET+TG | `src/paper_ablations/` source bundle and `scripts/run_paper_ablations.sh six-mode` | **Source uploaded; clean-clone execution and manuscript-table matching pending** |
| Pure 1-biplex / 2-biplex termination, no TG | `runners/MBE_PURE_ET1_ET2.zip`, `src/pure_et1_et2/`, `scripts/run_pure_13.sh` | Reproduction entry point available (six modes, five repeats) |
| Independently executed published IPS comparator, if reported | Original IPS native driver staged in pinned source-only ZIP | **Source uploaded; this is a count-aggregation protocol requiring separate validation** |

The two available timing campaigns have different timer and output-processing
contracts; internal search times must not be directly ranked across campaigns.
Single and Double internal search timer boundaries can also differ.

Before describing this as a complete EAB submission artifact:

1. Restore the graphs on a fresh clone and verify all six parts listed in `data/ARCHIVE_PARTS.json`.
2. Check each remaining manuscript table against its frozen implementation, precise
   compile switches, input SHA-256, mode configuration and five-repeat driver.
3. Verify the already staged campaign source and entry points reproduce the final
   reported configurations; exclude abandoned development revisions.
4. Verify permission to redistribute third-party data and upstream code; add
   accurate download sources, preprocessing instructions and license notices.
5. Pin a repository commit for the submission and verify clean-clone execution.

This is a **coverage checklist**, not a substitute for the omitted experiments.

The additional source is prepared as `src/paper_ablations/MBE_PAPER_ABLATIONS_FINAL_SOURCE_BUNDLE.zip` (SHA-256: `c6d1d8586cb5dff16ed3b87f35379e0c77e13a6533eb53774c26f6798ecb8995`). Use `python3 scripts/setup_paper_ablations.py` to extract it into Git-ignored `outputs/paper_suite/`, then `bash scripts/run_paper_ablations.sh check-source`. Documentation and script presence alone do not prove equivalence with final manuscript time measurements.
