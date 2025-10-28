"""テンプレート探索ロジックへのファサード。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from . import templates
from .models import TemplateInstallationCandidate


@dataclass(slots=True)
class TemplateGateway:
    """テンプレート探索関数をラップして依存を局所化する。"""

    def list_templates(self) -> List[Dict[str, str]]:
        return templates.list_templates()

    def discover_installations(self, template_id: str) -> List[TemplateInstallationCandidate]:
        return templates.discover_installations(template_id)
