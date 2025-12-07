"""
Adapters d'infrastructure.

Implementations des ports du domaine pour
les frameworks externes (Streamlit, etc).

Adapters disponibles:
---------------------
- StreamlitTenantContext: Contexte depuis session Streamlit
- NullTenantContext: Contexte sans restriction (tests)
"""

from src.infrastructure.adapters.streamlit_tenant_context import (
    StreamlitTenantContext,
)
from src.infrastructure.adapters.null_tenant_context import (
    NullTenantContext,
)

__all__ = [
    "StreamlitTenantContext",
    "NullTenantContext",
]
