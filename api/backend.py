"""
Mortgage Agent MVP - Data Access Layer
Connects to Delta tables via SQL warehouse using databricks-sql-connector.

This runs on the Databricks Apps runtime (Python 3.11, no Spark).
All data access goes through: databricks.sql.connect() + Config() + DATABRICKS_WAREHOUSE_ID

The warehouse ID is injected via app.yaml valueFrom: sql-warehouse.
"""

import os
import uuid
from typing import Optional

from databricks.sdk.core import Config
from databricks import sql


CATALOG = os.getenv("CATALOG", "workspace")
SCHEMA = os.getenv("SCHEMA", "mortgage_agent")
USE_MOCK = os.getenv("USE_MOCK_BACKEND", "false").lower() == "true"


def _table(name: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{name}"

def get_backend():
    """Factory: MockBackend when USE_MOCK_BACKEND=true, else WarehouseBackend."""
    if USE_MOCK:
        print("Backend: MOCK (in-memory)")
        return MockBackend()
    print("Backend: SQL WAREHOUSE (Delta tables)")
    return WarehouseBackend()

class WarehouseBackend:
    """
    Production backend: queries Delta tables through a Databricks SQL warehouse.
    Uses databricks-sql-connector with SDK Config() for auth.
    """

    def __init__(self):
        self._cfg = Config()
        self._warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
        if not self._warehouse_id:
            raise ValueError(
                "DATABRICKS_WAREHOUSE_ID not set. "
                "Add a SQL warehouse resource in app.yaml with valueFrom: sql-warehouse"
            )
        self._http_path = f"/sql/1.0/warehouses/{self._warehouse_id}"

    def _get_conn(self):
        return sql.connect(
            server_hostname=self._cfg.host,
            http_path=self._http_path,
            credentials_provider=lambda: self._cfg.authenticate,
        )

    def _query(self, query_sql: str, params: dict = None) -> list[dict]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query_sql, params)
                if cur.description is None:
                    return []
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _exec(self, exec_sql: str, params: dict = None):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(exec_sql, params)

    # -- Users --
    def create_user(self, user_id: Optional[str] = None, **kwargs) -> str:
        uid = user_id or str(uuid.uuid4())[:12]
        existing = self._query(
            f"SELECT id FROM {_table('users')} WHERE id = %(uid)s", {"uid": uid}
        )
        if existing:
            self._exec(
                f"UPDATE {_table('users')} SET updated_at = current_timestamp() WHERE id = %(uid)s",
                {"uid": uid},
            )
            if kwargs:
                self.update_user(uid, **kwargs)
        else:
            cols = ["id", "name", "income", "dp_amount", "location", "province",
                    "is_first_time", "purchase_type", "target_price"]
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
            }
            col_str = ", ".join(cols)
            val_str = ", ".join(f"%({c})s" for c in cols)
            self._exec(f"INSERT INTO {_table('users')} ({col_str}) VALUES ({val_str})", vals)
        return uid

    def get_user(self, user_id: str) -> Optional[dict]:
        rows = self._query(
            f"SELECT * FROM {_table('users')} WHERE id = %(uid)s", {"uid": user_id}
        )
        return rows[0] if rows else None

    def update_user(self, user_id: str, **kwargs):
        sets = []
        params = {"uid": user_id}
        for k, v in kwargs.items():
            if v is not None:
                param_key = f"p_{k}"
                sets.append(f"{k} = %({param_key})s")
                params[param_key] = v
        if sets:
            sets.append("updated_at = current_timestamp()")
            self._exec(
                f"UPDATE {_table('users')} SET {', '.join(sets)} WHERE id = %(uid)s",
                params,
            )

    # -- Sessions --
    def create_session(self, user_id: str) -> str:
        sid = str(uuid.uuid4())[:12]
        self._exec(
            f"INSERT INTO {_table('sessions')} (id, user_id) VALUES (%(sid)s, %(uid)s)",
            {"sid": sid, "uid": user_id},
        )
        return sid

    def get_session(self, session_id: str) -> Optional[dict]:
        rows = self._query(
            f"SELECT * FROM {_table('sessions')} WHERE id = %(sid)s",
            {"sid": session_id},
        )
        return rows[0] if rows else None

    # -- Messages --
    def add_message(self, session_id: str, role: str, content: str, tokens: int = 0):
        mid = str(uuid.uuid4())[:8]
        self._exec(
            f"INSERT INTO {_table('messages')} (id, session_id, role, content, tokens_used) "
            f"VALUES (%(mid)s, %(sid)s, %(role)s, %(content)s, %(tokens)s)",
            {"mid": mid, "sid": session_id, "role": role, "content": content, "tokens": tokens},
        )

    def get_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        return self._query(
            f"SELECT role, content FROM {_table('messages')} "
            f"WHERE session_id = %(sid)s ORDER BY created_at ASC LIMIT {limit}",
            {"sid": session_id},
        )

    # -- Knowledge --
    def get_all_topics(self) -> list[dict]:
        return self._query(
            f"SELECT * FROM {_table('knowledge_topics')} WHERE is_active = true ORDER BY sort_order"
        )

    def search_topics(self, query: str, limit: int = 3) -> list[dict]:
        q = query.lower()
        return self._query(
            f"SELECT * FROM {_table('knowledge_topics')} "
            f"WHERE is_active = true AND ("
            f"  lower(title) LIKE %(pattern)s "
            f"  OR lower(content) LIKE %(pattern)s "
            f"  OR array_contains(tags, %(tag)s)"
            f") ORDER BY sort_order LIMIT {limit}",
            {"pattern": f"%{q}%", "tag": q},
        )

    # -- Progress --
    def mark_topic_covered(self, user_id: str, topic_id: str, session_id: str = ""):
        existing = self._query(
            f"SELECT id FROM {_table('user_progress')} "
            f"WHERE user_id = %(uid)s AND topic_id = %(tid)s",
            {"uid": user_id, "tid": topic_id},
        )
        if not existing:
            pid = str(uuid.uuid4())[:8]
            self._exec(
                f"INSERT INTO {_table('user_progress')} (id, user_id, session_id, topic_id) "
                f"VALUES (%(pid)s, %(uid)s, %(sid)s, %(tid)s)",
                {"pid": pid, "uid": user_id, "sid": session_id, "tid": topic_id},
            )

    def get_progress(self, user_id: str) -> dict:
        covered = self._query(
            f"SELECT topic_id FROM {_table('user_progress')} WHERE user_id = %(uid)s",
            {"uid": user_id},
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

class MockBackend:
    """In-memory backend for local dev without any Databricks resources."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.progress: dict[str, set] = {}
        self.knowledge: list[dict] = []

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