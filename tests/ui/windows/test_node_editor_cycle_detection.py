"""ノード循環検出ロジックのテスト。"""

from __future__ import annotations

from dataclasses import dataclass, field

from sotugyo.ui.windows.views.node_editor import NodeEditorWindow


@dataclass(eq=False)
class _DummyNode:
    label: str
    outputs: list[_DummyNode] = field(default_factory=list)


class _CycleHarness:
    def _iter_downstream_nodes(self, node: _DummyNode):
        yield from node.outputs

    def _safe_node_name(self, node: _DummyNode) -> str:
        return node.label

    def _reconstruct_node_path(self, predecessors, end_node):
        return NodeEditorWindow._reconstruct_node_path(self, predecessors, end_node)


def test_find_cycle_path_self_loop() -> None:
    harness = _CycleHarness()
    node = _DummyNode("A")

    cycle = NodeEditorWindow._find_cycle_path_for_connection(harness, node, node)

    assert cycle == ["A", "A"]


def test_find_cycle_path_detects_existing_reachability() -> None:
    harness = _CycleHarness()
    source = _DummyNode("Source")
    mid = _DummyNode("Mid")
    target = _DummyNode("Target")
    target.outputs.append(mid)
    mid.outputs.append(source)

    cycle = NodeEditorWindow._find_cycle_path_for_connection(harness, source, target)

    assert cycle == ["Target", "Mid", "Source", "Target"]


def test_find_cycle_path_returns_none_when_no_cycle() -> None:
    harness = _CycleHarness()
    source = _DummyNode("Source")
    target = _DummyNode("Target")
    target.outputs.append(_DummyNode("Other"))

    cycle = NodeEditorWindow._find_cycle_path_for_connection(harness, source, target)

    assert cycle is None
