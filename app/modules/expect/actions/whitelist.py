# app/modules/expect/actions/whitelist.py
from typing import Dict, Any, Tuple, Optional, List

async def run_apply_whitelist(ip: str, _: List[str], profile: Dict[str, Any], auth_required: bool, user: str, password: str, max_ports: int, protocol: Optional[str] = None) -> Tuple[bool, str]:
    # 1. State is already updated in __init__.py before calling this, 
    # but we should ensure the sync happens.
    from .security import run_sync_security
    return await run_sync_security(ip, profile, auth_required, user, password, max_ports, protocol=protocol)
