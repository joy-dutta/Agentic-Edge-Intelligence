from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import numpy as np


def percentile(values: Iterable[float], quantile: float) -> float:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return float("nan")
    return float(np.quantile(array, quantile, method="higher"))


def parse_tripinfo(path: Path, emergency_id: str) -> tuple[dict[str, float | int | None], list[dict[str, float | str]]]:
    root = ET.parse(path).getroot()
    trips: list[dict[str, float | str]] = []
    for element in root.findall("tripinfo"):
        row: dict[str, float | str] = {"id": element.attrib["id"]}
        for key in (
            "depart",
            "arrival",
            "duration",
            "routeLength",
            "waitingTime",
            "timeLoss",
            "departDelay",
        ):
            row[key] = float(element.attrib.get(key, "nan"))
        trips.append(row)

    completed = [row for row in trips if float(row["arrival"]) >= 0]
    time_loss = [float(row["timeLoss"]) for row in completed]
    duration = [float(row["duration"]) for row in completed]
    emergency = next((row for row in completed if row["id"] == emergency_id), None)
    metrics: dict[str, float | int | None] = {
        "trips_recorded": len(trips),
        "completed_trips": len(completed),
        "unfinished_trips": len(trips) - len(completed),
        "mean_time_loss_s": float(np.mean(time_loss)) if time_loss else math.nan,
        "p95_time_loss_s": percentile(time_loss, 0.95),
        "p95_trip_time_s": percentile(duration, 0.95),
        "emergency_trip_time_s": float(emergency["duration"]) if emergency else None,
    }
    return metrics, trips


def parse_safety_statistics(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    safety = root.find("safety")
    teleports = root.find("teleports")
    vehicles = root.find("vehicles")
    return {
        "collisions": int(safety.attrib.get("collisions", 0)) if safety is not None else 0,
        "emergency_stops": int(safety.attrib.get("emergencyStops", 0)) if safety is not None else 0,
        "emergency_braking": int(safety.attrib.get("emergencyBraking", 0)) if safety is not None else 0,
        "teleports": int(teleports.attrib.get("total", 0)) if teleports is not None else 0,
        "teleports_jam": int(teleports.attrib.get("jam", 0)) if teleports is not None else 0,
        "teleports_yield": int(teleports.attrib.get("yield", 0)) if teleports is not None else 0,
        "teleports_wrong_lane": int(teleports.attrib.get("wrongLane", 0)) if teleports is not None else 0,
        "loaded_vehicles": int(vehicles.attrib.get("loaded", 0)) if vehicles is not None else 0,
        "inserted_vehicles": int(vehicles.attrib.get("inserted", 0)) if vehicles is not None else 0,
        "running_vehicles_at_end": int(vehicles.attrib.get("running", 0)) if vehicles is not None else 0,
        "waiting_vehicles_at_end": int(vehicles.attrib.get("waiting", 0)) if vehicles is not None else 0,
    }


def parse_ssm(path: Path) -> dict[str, float | int | None]:
    if not path.exists():
        return {
            "ssm_conflicts": 0,
            "ssm_unavailable_values": 0,
            "min_ttc_s": None,
            "min_pet_s": None,
            "max_drac_mps2": None,
        }
    root = ET.parse(path).getroot()
    conflicts = root.findall("conflict")
    ttc: list[float] = []
    pet: list[float] = []
    drac: list[float] = []
    unavailable_values = 0
    for conflict in conflicts:
        node = conflict.find("minTTC")
        if node is not None and node.attrib.get("value", "NA") != "NA":
            ttc.append(float(node.attrib["value"]))
        elif node is not None:
            unavailable_values += 1
        node = conflict.find("PET")
        if node is not None and node.attrib.get("value", "NA") != "NA":
            pet.append(float(node.attrib["value"]))
        elif node is not None:
            unavailable_values += 1
        node = conflict.find("maxDRAC")
        if node is not None and node.attrib.get("value", "NA") != "NA":
            drac.append(float(node.attrib["value"]))
        elif node is not None:
            unavailable_values += 1
    return {
        "ssm_conflicts": len(conflicts),
        "ssm_unavailable_values": unavailable_values,
        "min_ttc_s": min(ttc) if ttc else None,
        "min_pet_s": min(pet) if pet else None,
        "max_drac_mps2": max(drac) if drac else None,
    }
