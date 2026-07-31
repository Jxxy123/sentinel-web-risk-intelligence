"""
Provider selection for Sentinel Web-Risk Intelligence.

The factory keeps real and mock provider selection in one auditable place.
"""

from dataclasses import dataclass
from typing import Any

from core.brightdata import (
    serp_client,
    web_unlocker,
    proxy_client,
    mcp_client,
)
from core.config import settings
from core.mock_providers import (
    mock_serp_client,
    mock_web_unlocker,
    mock_proxy_client,
    mock_mcp_client,
)


@dataclass(frozen=True)
class WebProviderBundle:
    """Collection of web-intelligence providers used by one investigation."""

    serp: Any
    web_unlocker: Any
    proxy: Any
    mcp: Any
    execution_mode: str

    @property
    def is_mock(self) -> bool:
        """Return True when the bundle makes no external provider requests."""
        return self.execution_mode == "mock"


def get_web_providers() -> WebProviderBundle:
    """
    Return mock or real providers according to EXECUTION_MODE.

    Mock mode:
    - no Bright Data requests;
    - no proxy-network requests;
    - deterministic synthetic evidence.

    Real mode:
    - existing Bright Data integrations remain unchanged.
    """
    if settings.use_mock_providers:
        return WebProviderBundle(
            serp=mock_serp_client,
            web_unlocker=mock_web_unlocker,
            proxy=mock_proxy_client,
            mcp=mock_mcp_client,
            execution_mode="mock",
        )

    return WebProviderBundle(
        serp=serp_client,
        web_unlocker=web_unlocker,
        proxy=proxy_client,
        mcp=mcp_client,
        execution_mode="real",
    )
