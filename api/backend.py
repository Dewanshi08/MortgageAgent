"""
own-ly MVP - Data Access Layer

Two backends:
  MockBackend  - in-memory, for local dev (USE_MOCK_BACKEND=true)
  WarehouseBackend - Delta tables via SQL warehouse (production on Databricks)

Key fix from earlier debugging: databricks-sql-connector does NOT support
named parameters like %(name)s. We use inline string escaping via _esc().
"""

import os
import uuid
from typing import Optional

from api.knowledge import EMBEDDED_TOPICS

USE_MOCK = os.getenv("USE_MOCK_BACKEND", "false").lower() == "true"

CATALOG = os.getenv("CATALOG", "workspace")
SCHEMA = os.getenv("SCHEMA", "mortgage_agent")


def _table(name: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{name}"


def _esc(val) -> str:
    """Escape a value for inline SQL. Handles None, bool, numbers, strings."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    # String: escape single quotes
    return "'" + str(val).replace("'", "''") + "'"


def get_backend():
    """Factory: MockBackend when USE_MOCK_BACKEND=true, else WarehouseBackend."""
    if USE_MOCK:
        print("Backend: MOCK (in-memory)")
        return MockBackend()
    print("Backend: SQL WAREHOUSE (Delta tables)")
    return WarehouseBackend()


# ═══════════════════════════════════════════
# Warehouse Backend (Databricks SQL)
# ═══════════════════════════════════════════

class WarehouseBackend:
    """
    Production backend: queries Delta tables through a Databricks SQL warehouse.
    Uses databricks-sql-connector with SDK Config() for auth.
    Uses _esc() for parameter binding (connector doesn't support %(name)s).
    """

    def __init__(self):
        from databricks.sdk.core import Config
        from databricks import sql as dbsql
        self._sql = dbsql
        self._cfg = Config()
        self._warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
        if not self._warehouse_id:
            raise ValueError(
                "DATABRICKS_WAREHOUSE_ID not set. "
                "Add a SQL warehouse resource in app.yaml with valueFrom: sql-warehouse"
            )
        self._http_path = f"/sql/1.0/warehouses/{self._warehouse_id}"

    def _get_conn(self):
        return self._sql.connect(
            server_hostname=self._cfg.host,
            http_path=self._http_path,
            credentials_provider=lambda: self._cfg.authenticate,
        )

    def _query(self, query_sql: str) -> list[dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query_sql)
                if cur.description is None:
                    return []
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _exec(self, exec_sql: str):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(exec_sql)

    # -- Users --
    def create_user(self, user_id: Optional[str] = None, **kwargs) -> str:
        uid = user_id or str(uuid.uuid4())[:12]
        existing = self._query(
            f"SELECT id FROM {_table('users')} WHERE id = {_esc(uid)}"
        )
        if existing:
            self._exec(
                f"UPDATE {_table('users')} SET updated_at = current_timestamp() WHERE id = {_esc(uid)}"
            )
            if kwargs:
                self.update_user(uid, **kwargs)
        else:
            vals = {
                "id": uid,
                "name": kwargs.get("name", ""),
                "income": kwargs.get("income"),
                "dp_amount": kwargs.get("dp_amount"),
                "location": kwargs.get("location", "GTA"),
                "province": kwargs.get("province", "ON"),
                "is_first_time": kwargs.get("is_first_time", True),
                "purchase_type": kwargs.get("purchase_type", "pre-construction"),
                "target_price": kwargs.get("target_price"),
                "monthly_debts": kwargs.get("monthly_debts", 0),
            }
            cols = list(vals.keys()) + ["created_at", "updated_at"]
            col_str = ", ".join(cols)
            val_str = ", ".join(_esc(vals[c]) for c in vals.keys())
            val_str += ", current_timestamp(), current_timestamp()"
            self._exec(f"INSERT INTO {_table('users')} ({col_str}) VALUES ({val_str})")
        return uid

    def get_user(self, user_id: str) -> Optional[dict]:
        rows = self._query(
            f"SELECT * FROM {_table('users')} WHERE id = {_esc(user_id)}"
        )
        return rows[0] if rows else None

    def update_user(self, user_id: str, **kwargs):
        sets = []
        for k, v in kwargs.items():
            if v is not None:
                sets.append(f"{k} = {_esc(v)}")
        if sets:
            sets.append("updated_at = current_timestamp()")
            self._exec(
                f"UPDATE {_table('users')} SET {', '.join(sets)} WHERE id = {_esc(user_id)}"
            )

    # -- Sessions --
    def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())[:12]
        self._exec(
            f"INSERT INTO {_table('sessions')} (id, user_id, created_at) "
            f"VALUES ({_esc(sid)}, {_esc(user_id)}, current_timestamp())"
        )
        return sid

    def get_session(self, session_id: str) -> Optional[dict]:
        rows = self._query(
            f"SELECT * FROM {_table('sessions')} WHERE id = {_esc(session_id)}"
        )
        return rows[0] if rows else None

    # -- Messages --
    def add_message(self, session_id: str, role: str, content: str, tokens: int = 0):
        import base64
        mid = str(uuid.uuid4())[:8]
        # Base64-encode content to avoid SQL injection / special char issues
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        self._exec(
            f"INSERT INTO {_table('messages')} (id, session_id, role, content, tokens_used, created_at) "
            f"VALUES ({_esc(mid)}, {_esc(session_id)}, {_esc(role)}, {_esc(b64)}, {_esc(tokens)}, current_timestamp())"
        )

    def get_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        import base64
        rows = self._query(
            f"SELECT role, content FROM {_table('messages')} "
            f"WHERE session_id = {_esc(session_id)} ORDER BY created_at ASC LIMIT {limit}"
        )
        # Decode base64 content
        for r in rows:
            try:
                r["content"] = base64.b64decode(r["content"]).decode("utf-8")
            except Exception:
                pass  # If not base64 encoded (legacy), keep as-is
        return rows

    # -- Knowledge --
    def get_all_topics(self) -> list[dict]:
        return self._query(
            f"SELECT * FROM {_table('knowledge_topics')} WHERE is_active = true ORDER BY sort_order"
        )

    def search_topics(self, query: str, limit: int = 3) -> list[dict]:
        q = query.lower().replace("'", "''")
        return self._query(
            f"SELECT * FROM {_table('knowledge_topics')} "
            f"WHERE is_active = true AND ("
            f"  lower(title) LIKE '%{q}%' "
            f"  OR lower(content) LIKE '%{q}%' "
            f"  OR array_contains(tags, '{q}')"
            f") ORDER BY sort_order LIMIT {limit}"
        )

    # -- Progress --
    def mark_topic_covered(self, user_id: str, topic_id: str, session_id: str = ""):
        existing = self._query(
            f"SELECT id FROM {_table('user_progress')} "
            f"WHERE user_id = {_esc(user_id)} AND topic_id = {_esc(topic_id)}"
        )
        if not existing:
            pid = str(uuid.uuid4())[:8]
            self._exec(
                f"INSERT INTO {_table('user_progress')} (id, user_id, session_id, topic_id, covered_at) "
                f"VALUES ({_esc(pid)}, {_esc(user_id)}, {_esc(session_id)}, {_esc(topic_id)}, current_timestamp())"
            )

    def get_progress(self, user_id: str) -> dict:
        covered = self._query(
            f"SELECT topic_id FROM {_table('user_progress')} WHERE user_id = {_esc(user_id)}"
        )
        total_rows = self._query(
            f"SELECT count(*) as cnt FROM {_table('knowledge_topics')} WHERE is_active = true"
        )
        total = total_rows[0]["cnt"] if total_rows else 0
        covered_ids = [r["topic_id"] for r in covered]
        return {
            "topics_covered": len(covered_ids),
            "topics_total": total,
            "covered_ids": covered_ids,
            "completion_pct": round(len(covered_ids) / max(total, 1) * 100, 1),
        }


# ═══════════════════════════════════════════
# Mock Backend (Local Development)
# ═══════════════════════════════════════════

class MockBackend:
    """In-memory backend for local dev without any Databricks resources."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.progress: dict[str, set] = {}
        # Seed knowledge from embedded topics
        self.knowledge: list[dict] = [
            {**t, "is_active": True} for t in EMBEDDED_TOPICS
        ]

    # -- Users --
    def create_user(self, user_id=None, **kw):
        uid = user_id or str(uuid.uuid4())[:12]
        self.users[uid] = {"id": uid, **kw}
        return uid

    def get_user(self, uid):
        return self.users.get(uid)

    def update_user(self, uid, **kw):
        if uid in self.users:
            self.users[uid].update(kw)

    # -- Sessions --
    def create_session(self, uid):
        sid = str(uuid.uuid4())[:12]
        self.sessions[sid] = {"id": sid, "user_id": uid}
        self.messages[sid] = []
        return sid

    def get_session(self, sid):
        return self.sessions.get(sid)

    # -- Messages --
    def add_message(self, sid, role, content, tokens=0):
        self.messages.setdefault(sid, []).append({"role": role, "content": content})

    def get_messages(self, sid, limit=20):
        return (self.messages.get(sid) or [])[-limit:]

    # -- Knowledge --
    def get_all_topics(self):
        return self.knowledge

    def search_topics(self, query, limit=3):
        q = query.lower()
        scored = []
        for t in self.knowledge:
            s = sum(2 for tag in t.get("tags", []) if tag in q)
            if any(w in t.get("title", "").lower() for w in q.split()):
                s += 1
            if any(w in t.get("content", "").lower() for w in q.split() if len(w) > 3):
                s += 1
            if s > 0:
                scored.append((s, t))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:limit]]

    # -- Progress --
    def mark_topic_covered(self, uid, tid, sid=""):
        self.progress.setdefault(uid, set()).add(tid)

    def get_progress(self, uid):
        c = self.progress.get(uid, set())
        t = len(self.knowledge)
        return {
            "topics_covered": len(c),
            "topics_total": t,
            "covered_ids": list(c),
            "completion_pct": round(len(c) / max(t, 1) * 100, 1),
        }