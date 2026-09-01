from __future__ import annotations

import copy
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


def _unit_interval(seed: int, value: str) -> float:
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def scaled_route_file(
    source: Path,
    destination: Path,
    *,
    scale: float,
    seed: int,
) -> Path:
    """Create a deterministic route file with route proportions preserved."""
    if scale < 1.0:
        raise ValueError("Demand scaling below 1.0 is not used in this protocol")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if scale == 1.0:
        return source

    tree = ET.parse(source)
    root = tree.getroot()
    trips = list(root.findall("trip"))
    integer_copies = int(scale) - 1
    fractional = scale - int(scale)
    additions: list[ET.Element] = []

    for trip in trips:
        trip_id = trip.attrib["id"]
        copies = integer_copies
        if _unit_interval(seed, trip_id) < fractional:
            copies += 1
        for copy_index in range(copies):
            duplicate = copy.deepcopy(trip)
            duplicate.attrib["id"] = f"{trip_id}__scale_{copy_index + 1}"
            depart = float(duplicate.attrib["depart"])
            jitter = 0.25 + 0.5 * _unit_interval(seed, duplicate.attrib["id"])
            duplicate.attrib["depart"] = f"{depart + jitter:.2f}"
            additions.append(duplicate)

    all_trips = trips + additions
    all_trips.sort(key=lambda element: (float(element.attrib["depart"]), element.attrib["id"]))
    for trip in list(root.findall("trip")):
        root.remove(trip)
    for trip in all_trips:
        root.append(trip)

    ET.indent(tree, space="  ")
    tree.write(destination, encoding="utf-8", xml_declaration=True)
    return destination

