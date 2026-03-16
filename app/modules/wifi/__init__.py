from .wifi import (
    start, stop, restart, status, config,
    add_portal_user, remove_portal_user, list_portal_users,
    authorize_mac, deauthorize_mac
)

ALLOWED_ACTIONS = {
    "start": start,
    "stop": stop,
    "restart": restart,
    "status": status,
    "config": config,
    "add_portal_user": add_portal_user,
    "remove_portal_user": remove_portal_user,
    "list_portal_users": list_portal_users,
    "authorize_mac": authorize_mac,
    "deauthorize_mac": deauthorize_mac
}
