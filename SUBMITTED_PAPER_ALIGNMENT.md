# Alignment with the submitted paper

This audit uses the supplied PDF, *Search-State Optimization in Maximal
Biclique Enumeration: A Controlled Cross-Framework Study*, rather than later
Overleaf revisions. The PDF SHA-256 is
`2a672c793dd216d53bb35596e1187a169bd1ad2b25bde6088ee1d7080c163558`.
The public code reviewed was commit
`6fc92303d53a64f962d84fbf57ec91ca51202e90`. This patch was prepared from that
commit independently of the existing cache/resume development branch.

## Findings and changes

| Paper specification | Audit result |
|---|---|
| Single Candidate Tree Inline, Cursor and Pre-fork (III-B, Table III) | The existing algorithms implement the described transformations. No algorithm change was needed. The documented command now explicitly selects the four cumulative modes. |
| Result Tree layouts and compressed checksum reporting (III-B/C, Tables II/IV) | The checked implementations preserve output ownership and use ordinary materialization when tuples are requested. The Table II modes share count/XOR/SUM semantics. No reporting algorithm change was needed. |
| Double matching-oriented pivot (III-F, Eq. 12) | The guided source bundle could omit the missing-neighbor obstruction when sparse updates left its optional ID/list empty. Pivot selection now validates the cached unit defect and reconstructs it from exact candidate adjacency when necessary. Both copies of the guided source are updated identically. |
| Degree-one and degree-two guided modes in the pure runner | A hardcoded degree-two pivot threshold is replaced by the configured target degree. The optional cache reads its second missing ID only at defect count two, avoiding an invalid second-ID access at degree one. The six unguided Table VII modes retain their existing configuration. |
| Experimental environment (IV-A) | The thirteen-graph pure launcher now pins CPU 0 by default, validates the requested CPU, and permits an explicit `CPU` override. The other table commands explicitly request CPU 0. |
| Graphs and counts (Table I) | All 13 graph sizes and maximum degrees agree. The manifest now also records the paper's abbreviations and 13 reference biclique counts; the pure CSV validator rejects a common wrong count across all modes and requires positive finite search times. |
| Distinct guided and unguided studies (III-D/E/F, IV-E/F) | The README and command matrix now map Tables II-VII to their actual study drivers and distinguish the Table VI mask/matching campaign from the Table VII unguided degree-threshold campaign. |

The pure executable ZIP contains the same patched Double source as the readable
source tree. Only its `engine/two/ips.hpp` member changed. Only the two guided
`ips.hpp` members changed in the additional source bundle. The source-bundle
checksum and installer pin were updated together.

## Validation

The canonical inputs passed all file hashes, headers and edge-record checks
with `python3 scripts/verify_artifact.py --full-scan`.

Local native correctness checks compiled temporary copies with MSVC x64:

- 2,234 Single checks passed, including 528 graphs across Map, Inline, Cursor
  and Pre-fork, exact output sets, independent fingerprints, mask closure,
  ET1/ET2, prefix guidance, budget rejection and ordinary-recursion fallback.
- 16 Table II checks passed across MBET, MBETM, ST-noCR and ST+CR, two input
  orientations, and tuple output enabled/disabled, including multiword
  completions and independently computed count/XOR/SUM values.
- Double tests compare the actual instrumented C++ state counts and chosen
  pivots with an exact-adjacency reference, check Vector/Compact trace equality,
  and compare duplicate-free output sets against an exhaustive closure oracle.
  The reproducible verifier is `python3 scripts/verify_double_guidance.py`.
- Four CSV validation regressions passed. Bash syntax and mocked CPU selection
  checks passed. The source-bundle integrity check passed.

The temporary Windows adaptations supply compiler intrinsics and Linux header
compatibility; Single also uses a 64-bit `size_t` bit constant to match Linux's
LP64 semantics. These adaptations are confined to test copies. The released
Linux algorithms and compiler settings are unchanged by the adaptations.
The GitHub workflow repeats the packaged self-tests and the Double verifier
on Ubuntu 24.04 with GCC.

## Measurement limits

These are correctness and configuration checks, not a new thirteen-graph
performance campaign. The paper's reported timings remain historical
measurements of its original executables. Correcting a pivot can change the
search trajectory, terminal-hit counts and elapsed time; the repaired guided
build must be measured again before citing new performance numbers. This
patch does not rewrite the paper or adjust measurements to its reported values.

The sparse-cache regression uses a 9-by-12, 40-edge graph through the ordinary
production entry point. The original guided implementation chooses a pivot
that disagrees with the exact Eq. (12) reference on a state reached during
that search. The fixture is included in the verifier. This establishes a
policy mismatch; it does not establish an incorrect biclique output set or
quantify how often the thirteen benchmark graphs encounter the same condition.
