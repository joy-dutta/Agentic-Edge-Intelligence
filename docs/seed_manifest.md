# Seed Manifest

All sets are disjoint and frozen before confirmatory outcomes are viewed.

| Purpose | Seeds | Use |
|---|---:|---|
| IDQN training | 101-110 | Cycled deterministically across 100 episodes; episode 1 used 102 and episode 10 used 101 because RESCO's preserved training origin is zero |
| Nano/mini validation | 1001-1003 | Paired S2 model-sensitivity runs only |
| Pilot | 1101-1102 | Controller and measurement acceptance gates |
| Primary tests | 2101-2120 | Paired S0, S2, and S3 comparisons |
| Sensitivity tests | 3101-3110 | Paired S1 and S4 comparisons |
| Cologne-8 follow-up | 4101-4110 | Exploratory 1.3x-demand lane-closure comparison |
| Cologne-3 follow-up | 4201-4210 | Exploratory second-network holdout comparison |

The confirmatory run order is deterministically shuffled with seed `20260901`.
Model-validation sweep order uses `20260903` and `20260904`. These order seeds do
not alter SUMO demand generation. The separately preregistered follow-up uses run
order seed `20260902`; its seeds were frozen after the initial result but before
any follow-up execution and remain labelled exploratory.
