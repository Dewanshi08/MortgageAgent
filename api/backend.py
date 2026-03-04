import os
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from models.model import UserProfile, KnowledgeTopic


USE_MOCK = os.getenv("USE_MOCK_BACKEND", "true").lower() == "true"


class MockBackend:
    """In-memory backend for development without Lakebase."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.knowledge: list[dict] = []
        self.progress: dict[str, set] = {}
        self._seed_knowledge()

    def _seed_knowledge(self):
        """Seed with essential topics for mock mode."""
        from knowledge import EMBEDDED_TOPICS
        self.knowledge = EMBEDDED_TOPICS

    # ── Users ──

    def create_user(self, user_id: Optional[str] = None, **kwargs) -> str:
        uid = user_id or str(uuid.uuid4())[:12]
        self.users[uid] = {
            "id": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        return uid

    def get_user(self, user_id: str) -> Optional[dict]:
        return self.users.get(user_id)

    def update_user(self, user_id: str, **kwargs):
        if user_id in self.users:
            self.users[user_id].update(kwargs)

    # ── Sessions ──

    def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())[:12]
        self.sessions[sid] = {
            "id": sid,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "progress_json": {},
        }
        self.messages[sid] = []
        return sid

    def get_session(self, session_id: str) -> Optional[dict]:
        return self.sessions.get(session_id)

    # ── Messages ──

    def add_message(self, session_id: str, role: str, content: str, tokens: int = 0):
        if session_id not in self.messages:
            self.messages[session_id] = []
        self.messages[session_id].append({
            "id": str(uuid.uuid4())[:8],
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tokens_used": tokens,
        })

    def get_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        return (self.messages.get(session_id) or [])[-limit:]

    # ── Knowledge ──

    def get_all_topics(self) -> list[dict]:
        return self.knowledge

    def search_topics(self, query: str, limit: int = 3) -> list[dict]:
        query_lower = query.lower()
        scored = []
        for t in self.knowledge:
            score = 0
            for tag in t.get("tags", []):
                if tag in query_lower:
                    score += 2
            if any(w in t.get("title", "").lower() for w in query_lower.split()):
                score += 1
            if any(w in t.get("content", "").lower() for w in query_lower.split() if len(w) > 3):
                score += 0.5
            if score > 0:
                scored.append((score, t))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:limit]]

    # ── Progress ──

    def mark_topic_covered(self, user_id: str, topic_id: str, session_id: str = ""):
        key = user_id
        if key not in self.progress:
            self.progress[key] = set()
        self.progress[key].add(topic_id)

    def get_progress(self, user_id: str) -> dict:
        covered = self.progress.get(user_id, set())
        total = len(self.knowledge)
        return {
            "topics_covered": len(covered),
            "topics_total": total,
            "covered_ids": list(covered),
            "completion_pct": round(len(covered) / max(total, 1) * 100, 1),
        }


class LakebaseBackend:
    """Production backend using Lakebase (PostgreSQL)."""

    def __init__(self):
        import psycopg2
        self.conn = psycopg2.connect(
            host=os.getenv("PGHOST"),
            database=os.getenv("PGDATABASE"),
            user=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"),
            port=os.getenv("PGPORT", "5432"),
        )
        self.conn.autocommit = False

    def _execute(self, sql: str, params: tuple = (), fetch: bool = True):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch:
                cols = [d[0] for d in cur.description] if cur.description else []
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            self.conn.commit()
            return []

    # ── Users ──

    def create_user(self, user_id: Optional[str] = None, **kwargs) -> str:
        uid = user_id or str(uuid.uuid4())[:12]
        fields = ["id"] + list(kwargs.keys())
        placeholders = ["%s"] * len(fields)
        values = [uid] + list(kwargs.values())
        self._execute(
            f"INSERT INTO users ({', '.join(fields)}) VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT (id) DO UPDATE SET updated_at = now()",
            tuple(values), fetch=False,
        )
        return uid

    def get_user(self, user_id: str) -> Optional[dict]:
        rows = self._execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return rows[0] if rows else None

    def update_user(self, user_id: str, **kwargs):
        sets = ", ".join(f"{k} = %s" for k in kwargs.keys())
        vals = list(kwargs.values()) + [user_id]
        self._execute(
            f"UPDATE users SET {sets}, updated_at = now() WHERE id = %s",
            tuple(vals), fetch=False,
        )

    # ── Sessions ──

    def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())[:12]
        self._execute(
            "INSERT INTO sessions (id, user_id) VALUES (%s, %s)",
            (sid, user_id), fetch=False,
        )
        return sid

    def get_session(self, session_id: str) -> Optional[dict]:
        rows = self._execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
        return rows[0] if rows else None

    # ── Messages ──

    def add_message(self, session_id: str, role: str, content: str, tokens: int = 0):
        mid = str(uuid.uuid4())[:8]
        self._execute(
            "INSERT INTO messages (id, session_id, role, content, tokens_used) "
            "VALUES (%s, %s, %s, %s, %s)",
            (mid, session_id, role, content, tokens), fetch=False,
        )

    def get_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        return self._execute(
            "SELECT role, content FROM messages WHERE session_id = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (session_id, limit),
        )[::-1]

    # ── Knowledge ──

    def get_all_topics(self) -> list[dict]:
        return self._execute(
            "SELECT * FROM knowledge_topics WHERE is_active = TRUE ORDER BY sort_order"
        )

    def search_topics(self, query: str, limit: int = 3) -> list[dict]:
        return self._execute(
            "SELECT * FROM knowledge_topics WHERE is_active = TRUE "
            "AND (title ILIKE %s OR content ILIKE %s OR %s = ANY(tags)) "
            "ORDER BY sort_order LIMIT %s",
            (f"%{query}%", f"%{query}%", query.lower(), limit),
        )

    # ── Progress ──

    def mark_topic_covered(self, user_id: str, topic_id: str, session_id: str = ""):
        pid = str(uuid.uuid4())[:8]
        self._execute(
            "INSERT INTO user_progress (id, user_id, topic_id, session_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (user_id, topic_id) DO NOTHING",
            (pid, user_id, topic_id, session_id), fetch=False,
        )

    def get_progress(self, user_id: str) -> dict:
        covered = self._execute(
            "SELECT topic_id FROM user_progress WHERE user_id = %s", (user_id,)
        )
        total_rows = self._execute(
            "SELECT count(*) as cnt FROM knowledge_topics WHERE is_active = TRUE"
        )
        total = total_rows[0]["cnt"] if total_rows else 0
        covered_ids = [r["topic_id"] for r in covered]
        return {
            "topics_covered": len(covered_ids),
            "topics_total": total,
            "covered_ids": covered_ids,
            "completion_pct": round(len(covered_ids) / max(total, 1) * 100, 1),
        }


def get_backend():
    """Factory: returns MockBackend or LakebaseBackend based on env."""
    if USE_MOCK:
        return MockBackend()
    return LakebaseBackend()