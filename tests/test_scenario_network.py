import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ojcoms_poc.network import NetworkEmulator, NetworkProfile
from ojcoms_poc.scenario import scaled_route_file
from ojcoms_poc.topology import load_neighbors


def test_route_scaling_is_deterministic_and_sorted(tmp_path):
    source = tmp_path / "source.rou.xml"
    source.write_text(
        '<routes><trip id="a" depart="10" from="x" to="y"/>'
        '<trip id="b" depart="20" from="x" to="z"/></routes>',
        encoding="utf-8",
    )
    first = scaled_route_file(source, tmp_path / "first.xml", scale=1.5, seed=7)
    second = scaled_route_file(source, tmp_path / "second.xml", scale=1.5, seed=7)
    assert first.read_bytes() == second.read_bytes()
    trips = ET.parse(first).getroot().findall("trip")
    departures = [float(item.attrib["depart"]) for item in trips]
    assert departures == sorted(departures)
    assert len({item.attrib["id"] for item in trips}) == len(trips)


def test_scale_one_reuses_unmodified_source(tmp_path):
    source = tmp_path / "source.xml"
    source.write_text("<routes/>", encoding="utf-8")
    assert scaled_route_file(source, tmp_path / "unused.xml", scale=1, seed=1) == source


def test_network_emulator_is_seeded_and_separates_byte_definitions():
    profile = NetworkProfile("N", 80, 10, 0, 20)
    left = NetworkEmulator(profile, 42).transmit({"b": 2, "a": 1}, 100)
    right = NetworkEmulator(profile, 42).transmit({"a": 1, "b": 2}, 100)
    assert left == right
    assert left.application_bytes == len(b'{"a":1,"b":2}')
    assert left.modeled_transport_bytes > left.application_bytes
    assert left.deliver_at_s is not None and left.deliver_at_s > 100


def test_forced_outage_drops_without_claiming_wire_bytes():
    tx = NetworkEmulator(NetworkProfile("N", 10, 0, 0, 100), 1).transmit(
        {"state": 1}, 0, forced_outage=True
    )
    assert tx.dropped and tx.reason == "outage"
    assert tx.modeled_transport_bytes == 0


def test_load_neighbors_for_second_resco_network(tmp_path):
    signal = tmp_path / "signal.yaml"
    signal.write_text(
        """
cologne3:
  cluster_2415878664_254486231_359566_359576:
    downstream: {E: '360086'}
  '360086':
    downstream:
      E: '360082'
      W: cluster_2415878664_254486231_359566_359576
  '360082':
    downstream: {W: '360086'}
""".strip(),
        encoding="utf-8",
    )
    neighbors = load_neighbors(signal, "cologne3")

    assert set(neighbors) == {
        "cluster_2415878664_254486231_359566_359576",
        "360086",
        "360082",
    }
    assert neighbors["360086"] == {
        "cluster_2415878664_254486231_359566_359576",
        "360082",
    }
