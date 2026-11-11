# Publication readiness checklist (results-free core)

- [ ] Confirm permission to redistribute all 13 cleaned graph files and include required source attribution and notices.
- [ ] Confirm licensing and attribution for MBET- and IPS-derived code.
- [ ] Run `python3 scripts/prepare_data.py` and `python3 scripts/verify_artifact.py`.
- [ ] Run `python3 scripts/check_release.py`; manually check for private details or credentials.
- [ ] Run the two runner self-tests and at least one representative benchmark mode.
- [ ] Confirm the code/compilation options match the actual evaluated configurations.
- [ ] Add the final reproducibility code for Candidate Tree, Result Tree/CR, Compact/Vector, and guided ET/TG before claiming that **all** experiments in the paper can be reproduced.
- [ ] Ensure repository access without GitHub authentication and preserve a fixed commit or release tag for the submission.
- [ ] Do not represent generated results as preloaded records: the repository intentionally contains no original run CSVs or logs.

A repository without precomputed timing CSVs can still allow rerunning the included code, but its current scope must be clearly described. A complete EAB artifact must cover every published table and figure, not only the two verified-core campaigns.
