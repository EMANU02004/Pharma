"""Audit log writer. Every sensitive action calls log_action()."""
from .db import execute


def log_action(user_id, action, target_type=None, target_id=None, details=None):
    """Insert an audit row inside the caller's current transaction."""
    execute(
        "INSERT INTO audit_log (user_id, action, target_type, target_id, details) "
        "VALUES (%s, %s, %s, %s, %s)",
        (user_id, action, target_type, target_id, (details or None) and str(details)[:500]),
    )
