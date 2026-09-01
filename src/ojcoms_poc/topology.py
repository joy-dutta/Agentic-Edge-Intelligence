from __future__ import annotations

from pathlib import Path

import yaml


def load_neighbors(signal_config: Path, network_name: str = "cologne8") -> dict[str, set[str]]:
    with signal_config.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    network = raw[network_name]
    signal_ids = [key for key, value in network.items() if isinstance(value, dict) and "downstream" in value]
    neighbors = {signal_id: set() for signal_id in signal_ids}
    for signal_id in signal_ids:
        for downstream in network[signal_id]["downstream"].values():
            if downstream is None or downstream not in neighbors:
                continue
            neighbors[signal_id].add(downstream)
            neighbors[downstream].add(signal_id)
    return neighbors

