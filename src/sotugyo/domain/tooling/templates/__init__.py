"""テンプレート関連 API。"""

from .catalog import discover_installations, list_templates
from .gateway import TemplateGateway

__all__ = ["TemplateGateway", "discover_installations", "list_templates"]
