# Frozen 100-Episode IDQN Checkpoint

These files preserve the trained RESCO independent deep Q-network used in the separate placement sensitivity check.

| File or pattern | What it contains |
|---|---|
| `agt_<junction>.pt` | Seven PyTorch policy files, one for each individually represented Cologne-8 signal. |
| `agt_cluster_1098574052_1098574061_247379905.pt` | The policy file for the clustered signal identifier. |
| `learning_curve.csv` | Episode number, training seed, reward, and best-so-far reward for all 100 episodes. |
| `resco_training_config.json` | The frozen RESCO training and network configuration. Portable repository paths replace the original temporary working directory. |
| `manifest.json` | RESCO commit, episode count, training seeds, exclusion note, and SHA-256 hashes for the checkpoint payloads. |

Install the optional dependencies and inspect the evaluation command with:

```bash
python -m pip install -r requirements/idqn.lock
python scripts/resco_idqn.py --help
```

Summarize completed placement runs with `python scripts/analyze_idqn.py`. The released outputs are `data/processed/idqn_placement_results.csv` and the two `idqn_placement_*.csv` tables under `artifacts/tables`.
