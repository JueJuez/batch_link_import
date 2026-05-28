import json
import os
from datetime import datetime
from typing import List, Dict, Optional

PENDING_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pending_results.json",
)


def save_session_results(items: List[Dict]) -> str:
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "uploaded": False,
        "items": items,
    }
    sessions = _load_all()
    sessions.append(session)
    _write_all(sessions)
    return session_id


def has_pending() -> bool:
    sessions = _load_all()
    return any(not s.get("uploaded") for s in sessions)


def pending_count() -> int:
    sessions = _load_all()
    total = 0
    for s in sessions:
        if not s.get("uploaded"):
            total += len(s.get("items", []))
    return total


def pending_sessions_info() -> List[Dict]:
    sessions = _load_all()
    result = []
    for s in sessions:
        if not s.get("uploaded"):
            result.append({
                "session_id": s["session_id"],
                "created_at": s["created_at"],
                "count": len(s.get("items", [])),
            })
    return result


def load_latest_session() -> Optional[List[Dict]]:
    sessions = _load_all()
    for session in reversed(sessions):
        if not session.get("uploaded"):
            return session.get("items", [])
    return None


def load_all_pending() -> List[Dict]:
    sessions = _load_all()
    all_items = []
    for session in sessions:
        if not session.get("uploaded"):
            all_items.extend(session.get("items", []))
    return all_items


def mark_session_uploaded(session_id: str) -> None:
    sessions = _load_all()
    for session in sessions:
        if session["session_id"] == session_id:
            session["uploaded"] = True
    _write_all(sessions)


def mark_all_uploaded() -> int:
    sessions = _load_all()
    count = 0
    for session in sessions:
        if not session.get("uploaded"):
            session["uploaded"] = True
            count += len(session.get("items", []))
    _write_all(sessions)
    return count


def _load_all() -> List[Dict]:
    if not os.path.exists(PENDING_FILE):
        return []
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _write_all(sessions: List[Dict]) -> None:
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)