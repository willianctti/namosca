"""Testes das ferramentas de preparação dos dados FlyWire e MANC."""

from __future__ import annotations

import argparse
import csv
import gzip
import zipfile
from pathlib import Path

from tools.prepare_flywire_graph import build_graph
from tools.prepare_manc_motor_catalog import build_catalog


def _write_csv(path: Path, fieldnames: list[str], records: list[dict[str, object]]) -> None:
    """Grava registros de teste em um CSV compactado."""

    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def test_prepare_flywire_graph_joins_swc_metadata_and_edges(tmp_path: Path) -> None:
    """Confere a junção de metadados SWC e arestas no grafo."""

    archive_path = tmp_path / "skeletons.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "100.swc",
            "# PointNo Label X Y Z Radius Parent\n"
            "1 1 10 20 30 1 -1\n"
            "2 0 11 21 31 1 1\n",
        )
        archive.writestr(
            "200.swc",
            "# PointNo Label X Y Z Radius Parent\n"
            "1 1 40 50 60 1 -1\n",
        )
        archive.writestr(
            "300.swc",
            "# PointNo Label X Y Z Radius Parent\n"
            "1 1 70 80 90 1 -1\n",
        )

    neurons_path = tmp_path / "neurons.csv.gz"
    _write_csv(
        neurons_path,
        ["root_id", "group", "nt_type", "nt_type_score"],
        [
            {"root_id": "100", "group": "ME", "nt_type": "ACH", "nt_type_score": "0.9"},
            {"root_id": "200", "group": "ME", "nt_type": "GABA", "nt_type_score": "0.8"},
            {"root_id": "300", "group": "ME", "nt_type": "ACH", "nt_type_score": "0.7"},
        ],
    )
    cell_types_path = tmp_path / "cell_types.csv.gz"
    _write_csv(
        cell_types_path,
        ["root_id", "primary_type", "additional_type(s)"],
        [{"root_id": "100", "primary_type": "T1", "additional_type(s)": ""}],
    )
    connections_path = tmp_path / "connections.csv.gz"
    _write_csv(
        connections_path,
        ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"],
        [
            {"pre_root_id": "100", "post_root_id": "200", "neuropil": "ME_L", "syn_count": "10", "nt_type": "GABA"},
            {"pre_root_id": "200", "post_root_id": "300", "neuropil": "ME_L", "syn_count": "7", "nt_type": "ACH"},
            {"pre_root_id": "100", "post_root_id": "300", "neuropil": "ME_L", "syn_count": "2", "nt_type": "ACH"},
        ],
    )

    graph = build_graph(
        argparse.Namespace(
            skeletons=archive_path,
            neurons=neurons_path,
            cell_types=cell_types_path,
            connections=connections_path,
            output=tmp_path / "graph.json",
            group=["ME"],
            neuropil=["ME_L"],
            min_synapses=5,
            max_neurons=3,
            max_synapses=10,
            region="optic_lobes",
        )
    )

    assert graph["source"] == "flywire"
    assert graph["coordinate_space"] == "swc_nanometers"
    assert {neuron["id"] for neuron in graph["neurons"]} == {"100", "200", "300"}
    by_id = {neuron["id"]: neuron for neuron in graph["neurons"]}
    assert by_id["100"]["cell_type"] == "T1"
    assert graph["synapses"][0]["source"] == "100"
    assert graph["synapses"][0]["target"] == "200"
    assert graph["synapses"][0]["synapse_count"] == 10
    assert graph["synapses"][0]["inhibitory"] is True
    assert graph["metadata"]["counts"]["filtered_connection_rows"] == 2


def test_manc_motor_catalog_groups_leg_motors_and_descending_inputs(tmp_path: Path) -> None:
    """Confere o agrupamento de motores de perna e entradas descendentes."""

    attributes_path = tmp_path / "attributes.csv.gz"
    _write_csv(
        attributes_path,
        [
            "Root ID", "Top in/out region", "Flow", "Super Class", "Class",
            "Sub Class", "Nerve", "Soma side", "Primary Cell Type",
            "Predicted NT type", "Predicted NT confidence",
        ],
        [
            {"Root ID": "10", "Flow": "efferent", "Super Class": "motor", "Class": "fl", "Sub Class": "MN-LegNpT1", "Nerve": "ProLN_R", "Primary Cell Type": "MNfl01", "Predicted NT type": "GLUT"},
            {"Root ID": "20", "Flow": "afferent", "Super Class": "descending", "Class": "lt", "Sub Class": "DN-brain", "Nerve": "CvC", "Primary Cell Type": "DN01"},
            {"Root ID": "30", "Flow": "efferent", "Super Class": "motor", "Class": "wm", "Sub Class": "MN-wing", "Nerve": "ADMN_R", "Primary Cell Type": "MNwm01"},
        ],
    )
    connections_path = tmp_path / "connections.csv.gz"
    _write_csv(
        connections_path,
        ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"],
        [{"pre_root_id": "20", "post_root_id": "10", "neuropil": "LegNp_T1_R", "syn_count": "12", "nt_type": ""}],
    )

    catalog = build_catalog(attributes_path, connections_path)
    assert catalog["counts"]["motor_neurons"] == 2
    assert catalog["counts"]["descending_neurons"] == 1
    assert catalog["counts"]["motor_target_systems"] == {"front_leg": 1, "wing": 1}
    motor = next(item for item in catalog["motor_neurons"] if item["root_id"] == "10")
    assert motor["direct_descending_input_synapses"] == 12
