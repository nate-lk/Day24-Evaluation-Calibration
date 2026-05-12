# Test set manual review (Lab 24 A.1)

Reviewed **10** rows from `testset_v1.csv` (indices 0–9).

| Row | Issue | Action |
|-----|-------|--------|
| 0 | OK | kept |
| 1 | OK | kept |
| 2 | Wording ambiguous | kept (acceptable) |
| 3 | OK | kept |
| 4 | OK | kept |
| 5 | OK | kept |
| 6 | OK | kept |
| 7 | OK | kept |
| 8 | OK | kept |
| 9 | Question phrasing too close to ground-truth paste | **Edited** in CSV: tightened to ask for “điều kiện chính” only |

**Evidence of edit:** row 9 `question` field was changed from the auto-generated variant to a shorter form before freezing `testset_v1.csv` for grading. Regenerate with `python scripts/generate_testset.py` then re-apply this edit if the file is rebuilt.

**Distribution check:** after generation run:

`python -c "import pandas as pd; print(pd.read_csv('phase-a/testset_v1.csv')['evolution_type'].value_counts())"`

Expect roughly **50% simple**, **25% reasoning**, **25% multi_context** (small off-by-one acceptable when N=50).
