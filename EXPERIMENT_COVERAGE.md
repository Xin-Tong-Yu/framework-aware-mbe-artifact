# Manuscript-to-artifact experiment coverage

This file maps the **experiment families** in the manuscript to executable
material in this repository. The repository intentionally has **no archived
benchmark-result CSVs**: scripts generate new outputs locally. Code availability
is not a claim that a reviewer will reproduce identical timings on other hardware.

| Manuscript experiment | Available executable material | Status |
|---|---|---|
| Thirteen cleaned-graph statistics | `data/`, `scripts/prepare_data.py`, `scripts/verify_artifact.py` | Available once all six archive parts are uploaded and checksum verification passes |
| MBET/MBETM versus Single ST-noCR/ST+CR | `runners/MBE_FAIR_MBET_2024.zip`, `src/fair_mbet/` | Reproduction entry point available (four modes, five repeats) |
| Single Candidate Tree map/inline/cursor/pre-fork | Not included | **Missing final experiment implementation and driver** |
| Single Result Tree layout and CR factorial ablation | Not included as a standalone matrix | **Missing final experiment implementation and driver** |
| Double Vector/Compact state factorial ablation | Not included as a standalone matrix | **Missing final experiment implementation and driver** |
| Incremental Single/Double ST, ET, ET+TG | Not included as a final controlled matrix | **Missing final experiment implementation and driver** |
| Pure 1-biplex / 2-biplex termination, no TG | `runners/MBE_PURE_ET1_ET2.zip`, `src/pure_et1_et2/`, `scripts/run_pure_13.sh` | Reproduction entry point available (six modes, five repeats) |
| Independently executed published IPS comparator, if reported | IPS-derived Double code exists only within the pure-ET package | **A standalone exact published-baseline driver is not provided** |

The two available timing campaigns have different timer and output-processing
contracts; internal search times must not be directly ranked across campaigns.
Single and Double internal search timer boundaries can also differ.

Before describing this as a complete EAB submission artifact:

1. Upload and validate all six parts listed in `data/ARCHIVE_PARTS.json`.
2. Map each remaining manuscript table to its frozen implementation, precise
   compile switches, input SHA-256, mode configuration and five-repeat driver.
3. Add those final source trees and executable entry points; exclude abandoned
   development revisions that were not used to generate the submitted tables.
4. Verify permission to redistribute third-party data and upstream code; add
   accurate download sources, preprocessing instructions and license notices.
5. Pin a repository commit for the submission and verify clean-clone execution.

This is a **coverage checklist**, not a substitute for the omitted experiments.
