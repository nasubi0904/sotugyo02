"""テンプレート探索ロジックへのファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..models import TemplateInstallationCandidate
from . import catalog


@dataclass(slots=True)
class TemplateGateway:
    """テンプレート探索関数をラップして依存を局所化する。"""

    def list_templates(self) -> List[Dict[str, str]]:
        return catalog.list_templates()

    def discover_installations(self, template_id: str) -> List[TemplateInstallationCandidate]:
        return catalog.discover_installations(template_id)

    def load_environment_payload(self, template_id: str) -> Dict[str, object]:
        return catalog.load_environment_payload(template_id)
