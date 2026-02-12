from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sotugyo.ui.windows.views.node_editor import NodeEditorWindow


@dataclass(frozen=True)
class _Node:
    name: str


class _Harness:
    def __init__(self, graph: dict[_Node, list[_Node]], local_copies: dict[_Node, Path]) -> None:
        self._graph = graph
        self._local_copies = local_copies
        self.created: list[Path] = []
        self.warnings: list[str] = []

    def _safe_node_name(self, node: _Node) -> str:
        return node.name

    def _sanitize_node_dir_name(self, name: str) -> str:
        return name

    def _collect_input_nodes(self, node: _Node) -> list[_Node]:
        return list(self._graph.get(node, []))

    def _resolve_junction_dir(self, parent_dir: Path, base_name: str, *, title: str):  # noqa: ARG002
        return parent_dir / base_name, base_name

    def _ensure_local_node_copy_with_prompt(self, node: _Node, *, local_root: Path, confirm_missing: bool):  # noqa: ARG002
        return self._local_copies.get(node)

    def _local_node_copy_path(self, node: _Node, *, local_root: Path):  # noqa: ARG002
        return self._local_copies.get(node)

    def _create_junction(self, link_path: Path, target_path: Path) -> None:  # noqa: ARG002
        self.created.append(link_path)

    def _show_warning_dialog(self, message: str) -> None:
        self.warnings.append(message)


def test_build_junction_tree_expands_shared_upstream_node_per_branch(tmp_path):
    source = _Node("source")
    branch_a = _Node("branch_a")
    branch_b = _Node("branch_b")
    tail = _Node("tail")

    graph = {
        tail: [branch_a, branch_b],
        branch_a: [source],
        branch_b: [source],
        source: [],
    }
    local_copies = {node: tmp_path / "local" / node.name for node in graph}
    harness = _Harness(graph=graph, local_copies=local_copies)
    root_dir = tmp_path / "root"

    result = NodeEditorWindow._build_junction_tree(
        harness,
        root_dir,
        tail,
        local_root=tmp_path / "local",
        confirm_missing=False,
        skip_root_junction=True,
        ensure_local_copy=False,
        created_relative_paths=set(),
    )

    assert result in {root_dir / "branch_a", root_dir / "branch_b"}
    assert len(harness.created) == 4
    assert root_dir / "branch_a" / "source" in harness.created
    assert root_dir / "branch_b" / "source" in harness.created


def test_build_junction_tree_stops_on_cycle_without_infinite_recursion(tmp_path):
    node_a = _Node("A")
    node_b = _Node("B")

    graph = {
        node_a: [node_b],
        node_b: [node_a],
    }
    local_copies = {
        node_a: tmp_path / "local" / "A",
        node_b: tmp_path / "local" / "B",
    }
    harness = _Harness(graph=graph, local_copies=local_copies)
    root_dir = tmp_path / "root"

    result = NodeEditorWindow._build_junction_tree(
        harness,
        root_dir,
        node_a,
        local_root=tmp_path / "local",
        confirm_missing=False,
        skip_root_junction=False,
        ensure_local_copy=False,
        created_relative_paths=set(),
    )

    assert result == root_dir / "A"
    assert harness.created == [root_dir / "A", root_dir / "A" / "B"]
