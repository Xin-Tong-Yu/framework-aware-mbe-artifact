# Publication readiness checklist (results-free artifact)

- [ ] Confirm permission to redistribute all 13 cleaned graph files and include required source attribution and notices.
- [ ] Confirm licensing and attribution for MBET- and IPS-derived code.
- [ ] Run `python3 scripts/prepare_data.py` and `python3 scripts/verify_artifact.py`.
- [ ] Run `python3 scripts/check_release.py`; manually check for private details or credentials.
- [ ] Run the two runner self-tests and at least one representative benchmark mode.
- [ ] Confirm the code/compilation options match the actual evaluated configurations.
- [x] Stage source archive and launchers for Candidate Tree, Result Tree/CR, Compact/Vector, and guided ET/TG.
- [ ] From a fresh clone, execute each staged final campaign and reconcile mode configurations and output values with every manuscript table/figure. A passed source check does not substitute for full experimental verification.
- [ ] Ensure repository access without GitHub authentication and preserve a fixed commit or release tag for the submission.
- [ ] Do not represent generated results as preloaded records: the repository intentionally contains no original run CSVs or logs.

A repository without precomputed timing CSVs can still allow rerunning the included code, but its current scope must be clearly described. A complete EAB artifact must cover every published table and figure, including the additional staged campaign source; those campaigns remain unverified end-to-end.
