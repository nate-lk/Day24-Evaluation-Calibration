# Judge Bias Observations

## Bias 1: Position bias (Answer A listed first in run 1)

- `run1_winner == 'A'`: **0 / 5** = **0.0%**
- Expected ~50% if no position bias; >55% suggests first-slot favoritism.

## Bias 2: Length bias

| Metric | Value |
|--------|-------|
| B wins when B is longer | 0 / 0 = **0.0%** |
| A wins when A is longer | 0 / 1 = **0.0%** |

## Table: mean len_diff (B-A) by final winner

| winner_after_swap | mean len_diff (B-A) |
|---|---|
| tie | -5.6 |

## Mitigation strategy

- Keep **swap-and-average** for pairwise comparisons.
- Add **length-normalized** presentation to the judge (truncate both to same token budget) for future runs.
- Prefer **rubric-based absolute scoring** when stakes are high.
