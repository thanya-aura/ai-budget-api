def check_access(role, action):
    if role not in {"admin", "editor", "viewer", "approver"}:
        raise PermissionError("🚫 Invalid role")
    if role == "viewer" and action != "read":
        raise PermissionError("🚫 Viewers cannot perform this action.")