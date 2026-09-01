# Completed Experiment Checklist

- [x] RESCO commit and deterministic patch are pinned and checked before execution.
- [x] SUMO, Python, package, model-snapshot, prompt, policy, and container versions are recorded.
- [x] Training, validation, pilot, confirmatory, sensitivity, and follow-up seeds are disjoint.
- [x] The two-seed pilot was reviewed before the full sweep.
- [x] The 520-run confirmatory matrix contains every registered controller/scenario/seed cell.
- [x] The 80-run exploratory follow-up contains every registered cell on Cologne-8 and Cologne-3.
- [x] Live requests passed the strict eight-agent response contract.
- [x] The append-only budget ledger and persistent worst-case reservations were active.
- [x] Packet captures reconcile with application counters within the declared tolerance.
- [x] Exact replay reproduces the recorded summaries and decision hashes.
- [x] Frozen IDQN checkpoints and their SHA-256 manifest are present.
- [x] Repeatability, independent latency, policy-shield, and model-sensitivity audits are complete.
- [x] Paired bootstrap intervals, Wilcoxon tests, effect sizes, and Holm correction are recorded.
- [x] The public package includes processed data and tables but excludes private raw logs and packet captures.
- [x] The public release secret scan reports filenames only and never echoes matching values.

For the final publication steps, use [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
