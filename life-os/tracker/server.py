"""life tracker — authenticated local http api + web app. stdlib only.

run:  python3 server.py [--host 127.0.0.1] [--port 8787] [--db life_tracker.db]

auth has two identities on purpose:

  bearer token  -> the agent. full write access.
  cookie session -> the browser. reads, plus completing and reopening habits and tasks.

that split is the design, not a limitation. the web app is where you tick things off; the
agent is the write interface for goals, projects, metric definitions, observations,
corrections and interpretation. the `data` dashboard is read-only by construction — there
is no endpoint a browser session can reach that would let it invent a number.
"""

from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import sys
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path

import db as store

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
SESSION_TTL_SECONDS = 60 * 60 * 12

# routes a browser session may call. everything else needs the bearer token.
WEB_WRITABLE = {
    ("POST", "habit_complete"), ("POST", "habit_reopen"),
    ("POST", "task_complete"), ("POST", "task_reopen"),
    ("POST", "session"), ("DELETE", "session"),
}


class ApiError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = status
        self.payload = {"error": message, **extra}


def load_token(explicit: str | None = None) -> str:
    """env var, then a local file, then generate one. never printed to logs."""
    tok = explicit or os.environ.get("LIFE_TRACKER_TOKEN")
    if tok:
        return tok
    path = HERE / ".token"
    if path.exists():
        return path.read_text().strip()
    tok = secrets.token_urlsafe(32)
    path.write_text(tok + "\n")
    os.chmod(path, 0o600)
    return tok


class Tracker:
    """all endpoint logic. one method per route, so the handler stays dumb."""

    def __init__(self, db_path: str, token: str):
        self.db_path = db_path
        self.token = token
        self.sessions: dict[str, float] = {}
        conn = store.connect(db_path)
        store.init(conn)
        conn.close()

    # -- helpers ----------------------------------------------------------------

    def _conn(self):
        return store.connect(self.db_path)

    def _resolve_date(self, conn, given):
        if given:
            try:
                return store.parse_date(given)
            except ValueError:
                raise ApiError(400, "date must be YYYY-MM-DD")
        today = store.today_in_tz(conn)
        if not today:
            raise ApiError(
                409,
                "timezone is not configured, so 'today' is undefined. "
                "set it with PATCH /api/settings {\"timezone\": \"Area/City\"} "
                "or pass an explicit ?date=YYYY-MM-DD.",
            )
        return store.parse_date(today)

    @staticmethod
    def _require(body, *fields):
        missing = [f for f in fields if body.get(f) in (None, "")]
        if missing:
            raise ApiError(400, f"missing required field(s): {', '.join(missing)}")

    # -- session ----------------------------------------------------------------

    def new_session(self, body):
        import time

        supplied = str(body.get("token", ""))
        if not hmac.compare_digest(supplied, self.token):
            raise ApiError(401, "invalid token")
        sid = secrets.token_urlsafe(32)
        self.sessions[sid] = time.time() + SESSION_TTL_SECONDS
        return {"ok": True}, sid

    def session_valid(self, sid):
        import time

        exp = self.sessions.get(sid)
        if not exp:
            return False
        if exp < time.time():
            self.sessions.pop(sid, None)
            return False
        return True

    # -- settings ---------------------------------------------------------------

    def get_settings(self, conn):
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        s = {r["key"]: r["value"] for r in rows}
        s["today"] = store.today_in_tz(conn)
        s["timezone_configured"] = bool(s.get("timezone"))
        return s

    def patch_settings(self, conn, body, actor):
        allowed = {"timezone", "user_name", "onboarded", "kb_path"}
        for k, v in body.items():
            if k not in allowed:
                raise ApiError(400, f"unknown setting: {k}")
            if k == "timezone":
                try:
                    from zoneinfo import ZoneInfo

                    ZoneInfo(str(v))
                except Exception:
                    raise ApiError(400, f"unknown timezone: {v}")
            store.set_setting(conn, k, str(v))
            store.audit(conn, actor, "set_setting", "settings", k, {"value": str(v)})
        conn.commit()
        return self.get_settings(conn)

    # -- today ------------------------------------------------------------------

    def today(self, conn, q):
        d = self._resolve_date(conn, q.get("date"))
        return store.today_view(conn, d)

    def habit_complete(self, conn, habit_id, body, actor):
        d = self._resolve_date(conn, body.get("date"))
        state = body.get("state", "completed")
        if state not in ("completed", "skipped"):
            raise ApiError(400, "state must be 'completed' or 'skipped'")
        h = conn.execute("SELECT * FROM habits WHERE id=? AND deleted_at IS NULL",
                         (habit_id,)).fetchone()
        if not h:
            raise ApiError(404, "habit not found")
        sub = int(body.get("subtask_id") or 0)
        if sub:
            ok = conn.execute("SELECT 1 FROM habit_subtasks WHERE id=? AND habit_id=? "
                              "AND deleted_at IS NULL", (sub, habit_id)).fetchone()
            if not ok:
                raise ApiError(404, "subtask not found on this habit")
        conn.execute(
            "INSERT INTO habit_completions(habit_id,subtask_id,date,state,note,recorded_at) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(habit_id,subtask_id,date) "
            "DO UPDATE SET state=excluded.state, note=excluded.note, "
            "recorded_at=excluded.recorded_at",
            (habit_id, sub, d.strftime(store.ISO), state, body.get("note"), store.now_utc()),
        )
        store.audit(conn, actor, "habit_" + state, "habit", habit_id,
                    {"date": d.strftime(store.ISO), "subtask_id": sub})
        conn.commit()
        return {"habit": store.habit_day_state(conn, h, d),
                "frequency": store.min_frequency_status(conn, h, d)}

    def habit_reopen(self, conn, habit_id, body, actor):
        d = self._resolve_date(conn, body.get("date"))
        sub = int(body.get("subtask_id") or 0)
        ds = d.strftime(store.ISO)
        prev = conn.execute(
            "SELECT state FROM habit_completions WHERE habit_id=? AND subtask_id=? AND date=?",
            (habit_id, sub, ds)).fetchone()
        if not prev:
            raise ApiError(404, "no completion recorded for that habit on that date")
        conn.execute("DELETE FROM habit_completions WHERE habit_id=? AND subtask_id=? AND date=?",
                     (habit_id, sub, ds))
        # the row goes, the fact that it existed does not.
        store.audit(conn, actor, "habit_reopen", "habit", habit_id,
                    {"date": ds, "subtask_id": sub, "previous_state": prev["state"]})
        conn.commit()
        h = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
        return {"habit": store.habit_day_state(conn, h, d)}

    def task_set_status(self, conn, task_id, done, body, actor):
        t = conn.execute("SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL",
                         (task_id,)).fetchone()
        if not t:
            raise ApiError(404, "task not found")
        if done:
            d = self._resolve_date(conn, body.get("date"))
            conn.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?",
                         (d.strftime(store.ISO), task_id))
        else:
            conn.execute("UPDATE tasks SET status='open', completed_at=NULL WHERE id=?",
                         (task_id,))
        store.audit(conn, actor, "task_done" if done else "task_reopen", "task", task_id,
                    {"previous_status": t["status"]})
        conn.commit()
        r = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(r)

    # -- goals ------------------------------------------------------------------

    def list_goals(self, conn):
        rows = conn.execute(
            "SELECT g.*, a.name AS area FROM goals g LEFT JOIN life_areas a ON a.id=g.area_id "
            "WHERE g.deleted_at IS NULL ORDER BY a.name, g.id").fetchall()
        out = []
        for g in rows:
            out.append({**dict(g), "progress": store.goal_progress(conn, g["id"]),
                        **self._goal_children(conn, g["id"])})
        return {"goals": out}

    def _goal_children(self, conn, goal_id):
        crit = conn.execute("SELECT * FROM success_criteria WHERE goal_id=? AND "
                            "deleted_at IS NULL ORDER BY sort_order, id", (goal_id,)).fetchall()
        ms = conn.execute("SELECT * FROM milestones WHERE goal_id=? AND deleted_at IS NULL "
                          "ORDER BY sort_order, id", (goal_id,)).fetchall()
        pr = conn.execute("SELECT id,title,status,phase FROM projects WHERE goal_id=? AND "
                          "deleted_at IS NULL", (goal_id,)).fetchall()
        hb = conn.execute("SELECT id,title,schedule_type,status FROM habits WHERE goal_id=? AND "
                          "deleted_at IS NULL", (goal_id,)).fetchall()
        nx = conn.execute("SELECT id,title,due_date FROM tasks WHERE goal_id=? AND status='open' "
                          "AND deleted_at IS NULL ORDER BY due_date IS NULL, due_date LIMIT 5",
                          (goal_id,)).fetchall()
        nxt_ms = next((dict(m) for m in ms if m["status"] != "done"), None)
        return {"criteria": [dict(c) for c in crit], "milestones": [dict(m) for m in ms],
                "next_milestone": nxt_ms, "projects": [dict(p) for p in pr],
                "habits": [dict(h) for h in hb], "next_actions": [dict(t) for t in nx]}

    def create_goal(self, conn, body, actor):
        self._require(body, "title")
        area_id = None
        if body.get("life_area"):
            conn.execute("INSERT OR IGNORE INTO life_areas(name,created_at) VALUES(?,?)",
                         (body["life_area"], store.now_utc()))
            area_id = conn.execute("SELECT id FROM life_areas WHERE name=?",
                                   (body["life_area"],)).fetchone()["id"]
        now = store.now_utc()
        cur = conn.execute(
            "INSERT INTO goals(area_id,title,outcome,definition_of_done,rationale,baseline,"
            "status,target_date,next_review,kb_path,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (area_id, body["title"], body.get("outcome"), body.get("definition_of_done"),
             body.get("rationale"), body.get("baseline"), body.get("status", "not_started"),
             body.get("target_date"), body.get("next_review"), body.get("kb_path"), now, now))
        gid = cur.lastrowid
        for i, c in enumerate(body.get("criteria", [])):
            conn.execute("INSERT INTO success_criteria(goal_id,description,metric_id,"
                         "target_value,comparator,sort_order) VALUES(?,?,?,?,?,?)",
                         (gid, c["description"] if isinstance(c, dict) else str(c),
                          (c.get("metric_id") if isinstance(c, dict) else None),
                          (c.get("target_value") if isinstance(c, dict) else None),
                          (c.get("comparator") if isinstance(c, dict) else None), i))
        for i, m in enumerate(body.get("milestones", [])):
            conn.execute("INSERT INTO milestones(goal_id,title,target_date,sort_order) "
                         "VALUES(?,?,?,?)",
                         (gid, m["title"] if isinstance(m, dict) else str(m),
                          (m.get("target_date") if isinstance(m, dict) else None), i))
        store.audit(conn, actor, "create", "goal", gid, {"title": body["title"]})
        conn.commit()
        return self.get_goal(conn, gid)

    def get_goal(self, conn, gid):
        g = conn.execute("SELECT g.*, a.name AS area FROM goals g "
                         "LEFT JOIN life_areas a ON a.id=g.area_id "
                         "WHERE g.id=? AND g.deleted_at IS NULL", (gid,)).fetchone()
        if not g:
            raise ApiError(404, "goal not found")
        return {**dict(g), "progress": store.goal_progress(conn, gid),
                **self._goal_children(conn, gid)}

    def patch_goal(self, conn, gid, body, actor):
        g = conn.execute("SELECT * FROM goals WHERE id=? AND deleted_at IS NULL",
                         (gid,)).fetchone()
        if not g:
            raise ApiError(404, "goal not found")
        fields = {k: v for k, v in body.items() if k in {
            "title", "outcome", "definition_of_done", "rationale", "baseline", "status",
            "status_reason", "target_date", "next_review", "kb_path"}}
        if fields.get("status") in ("paused", "abandoned", "blocked") and \
                not (fields.get("status_reason") or g["status_reason"]):
            raise ApiError(400, f"changing status to '{fields['status']}' requires a "
                                "status_reason — the reason is the part worth keeping")
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE goals SET {sets}, updated_at=? WHERE id=?",
                         (*fields.values(), store.now_utc(), gid))
            store.audit(conn, actor, "update", "goal", gid,
                        {"changed": list(fields), "previous_status": g["status"]})
        conn.commit()
        return self.get_goal(conn, gid)

    def add_criterion(self, conn, gid, body, actor):
        self._require(body, "description")
        cur = conn.execute("INSERT INTO success_criteria(goal_id,description,metric_id,"
                           "target_value,comparator,sort_order) VALUES(?,?,?,?,?,?)",
                           (gid, body["description"], body.get("metric_id"),
                            body.get("target_value"), body.get("comparator"),
                            body.get("sort_order", 0)))
        store.audit(conn, actor, "create", "criterion", cur.lastrowid, {"goal_id": gid})
        conn.commit()
        return self.get_goal(conn, gid)

    def patch_criterion(self, conn, cid, body, actor):
        c = conn.execute("SELECT * FROM success_criteria WHERE id=?", (cid,)).fetchone()
        if not c:
            raise ApiError(404, "criterion not found")
        met = 1 if body.get("met") else 0
        conn.execute("UPDATE success_criteria SET met=?, met_at=?, description=COALESCE(?,"
                     "description) WHERE id=?",
                     (met, body.get("met_at") if met else None, body.get("description"), cid))
        store.audit(conn, actor, "update", "criterion", cid, {"met": bool(met)})
        conn.commit()
        return self.get_goal(conn, c["goal_id"])

    def add_milestone(self, conn, body, actor):
        self._require(body, "title")
        if not body.get("goal_id") and not body.get("project_id"):
            raise ApiError(400, "milestone needs a goal_id or a project_id")
        cur = conn.execute("INSERT INTO milestones(goal_id,project_id,title,target_date,"
                           "sort_order) VALUES(?,?,?,?,?)",
                           (body.get("goal_id"), body.get("project_id"), body["title"],
                            body.get("target_date"), body.get("sort_order", 0)))
        store.audit(conn, actor, "create", "milestone", cur.lastrowid, {"title": body["title"]})
        conn.commit()
        return {"id": cur.lastrowid}

    def patch_milestone(self, conn, mid, body, actor):
        m = conn.execute("SELECT * FROM milestones WHERE id=?", (mid,)).fetchone()
        if not m:
            raise ApiError(404, "milestone not found")
        status = body.get("status", m["status"])
        conn.execute("UPDATE milestones SET status=?, completed_at=?, title=COALESCE(?,title), "
                     "target_date=COALESCE(?,target_date) WHERE id=?",
                     (status, body.get("completed_at") if status == "done" else None,
                      body.get("title"), body.get("target_date"), mid))
        store.audit(conn, actor, "update", "milestone", mid,
                    {"status": status, "previous": m["status"]})
        conn.commit()
        return {"id": mid, "status": status}

    # -- projects ---------------------------------------------------------------

    def list_projects(self, conn):
        rows = conn.execute("SELECT * FROM projects WHERE deleted_at IS NULL "
                            "ORDER BY status='active' DESC, id").fetchall()
        return {"projects": [self._project_payload(conn, p) for p in rows]}

    def _project_payload(self, conn, p):
        ms = conn.execute("SELECT * FROM milestones WHERE project_id=? AND deleted_at IS NULL "
                          "ORDER BY sort_order, id", (p["id"],)).fetchall()
        ts = conn.execute("SELECT * FROM tasks WHERE project_id=? AND deleted_at IS NULL "
                          "ORDER BY status='done', sort_order, id", (p["id"],)).fetchall()
        nxt = next((dict(t) for t in ts if t["status"] == "open"), None)
        return {**dict(p),
                "progress": store.project_progress(conn, p["id"]),
                "health": store.project_health(conn, p),
                "milestones": [dict(m) for m in ms],
                "tasks": [dict(t) for t in ts],
                "next_action": nxt}

    def create_project(self, conn, body, actor):
        self._require(body, "title")
        now = store.now_utc()
        cur = conn.execute(
            "INSERT INTO projects(goal_id,title,purpose,status,phase,owner,deadline,blocker,"
            "kb_path,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (body.get("goal_id"), body["title"], body.get("purpose"),
             body.get("status", "active"), body.get("phase"), body.get("owner"),
             body.get("deadline"), body.get("blocker"), body.get("kb_path"), now, now))
        pid = cur.lastrowid
        for i, t in enumerate(body.get("tasks", [])):
            conn.execute("INSERT INTO tasks(project_id,title,due_date,sort_order) "
                         "VALUES(?,?,?,?)",
                         (pid, t["title"] if isinstance(t, dict) else str(t),
                          (t.get("due_date") if isinstance(t, dict) else None), i))
        store.audit(conn, actor, "create", "project", pid, {"title": body["title"]})
        conn.commit()
        p = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return self._project_payload(conn, p)

    def patch_project(self, conn, pid, body, actor):
        p = conn.execute("SELECT * FROM projects WHERE id=? AND deleted_at IS NULL",
                         (pid,)).fetchone()
        if not p:
            raise ApiError(404, "project not found")
        fields = {k: v for k, v in body.items() if k in {
            "goal_id", "title", "purpose", "status", "status_reason", "phase", "owner",
            "deadline", "blocker", "kb_path"}}
        if fields.get("status") in ("paused", "abandoned") and \
                not (fields.get("status_reason") or p["status_reason"]):
            raise ApiError(400, f"changing status to '{fields['status']}' requires a "
                                "status_reason")
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE projects SET {sets}, updated_at=? WHERE id=?",
                         (*fields.values(), store.now_utc(), pid))
            store.audit(conn, actor, "update", "project", pid, {"changed": list(fields)})
        conn.commit()
        p = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return self._project_payload(conn, p)

    def create_task(self, conn, body, actor):
        self._require(body, "title")
        cur = conn.execute(
            "INSERT INTO tasks(project_id,goal_id,milestone_id,parent_id,title,due_date,"
            "blocked_reason,sort_order) VALUES(?,?,?,?,?,?,?,?)",
            (body.get("project_id"), body.get("goal_id"), body.get("milestone_id"),
             body.get("parent_id"), body["title"], body.get("due_date"),
             body.get("blocked_reason"), body.get("sort_order", 0)))
        store.audit(conn, actor, "create", "task", cur.lastrowid, {"title": body["title"]})
        conn.commit()
        return dict(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())

    def patch_task(self, conn, tid, body, actor):
        t = conn.execute("SELECT * FROM tasks WHERE id=? AND deleted_at IS NULL",
                         (tid,)).fetchone()
        if not t:
            raise ApiError(404, "task not found")
        fields = {k: v for k, v in body.items() if k in {
            "title", "status", "due_date", "blocked_reason", "project_id", "goal_id",
            "milestone_id", "sort_order", "completed_at"}}
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", (*fields.values(), tid))
            store.audit(conn, actor, "update", "task", tid, {"changed": list(fields)})
        conn.commit()
        return dict(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())

    # -- habits -----------------------------------------------------------------

    VALID_SCHEDULES = {"daily", "weekdays", "interval", "min_frequency", "weekly"}

    def list_habits(self, conn):
        rows = conn.execute("SELECT * FROM habits WHERE deleted_at IS NULL ORDER BY id").fetchall()
        return {"habits": [{**dict(h),
                            "subtasks": [dict(s) for s in store.subtasks_of(conn, h["id"])]}
                           for h in rows]}

    def create_habit(self, conn, body, actor):
        self._require(body, "title", "schedule_type")
        st = body["schedule_type"]
        if st not in self.VALID_SCHEDULES:
            raise ApiError(400, f"schedule_type must be one of {sorted(self.VALID_SCHEDULES)}")
        cfg = body.get("schedule_config", {})
        if st == "weekdays" and not cfg.get("days"):
            raise ApiError(400, "weekdays schedule needs schedule_config.days (0=monday)")
        if st == "interval" and not cfg.get("every_n_days"):
            raise ApiError(400, "interval schedule needs schedule_config.every_n_days")
        if st in ("min_frequency", "weekly") and not cfg.get("times"):
            raise ApiError(400, "minimum-frequency schedule needs schedule_config.times")
        now = store.now_utc()
        cur = conn.execute(
            "INSERT INTO habits(title,schedule_type,schedule_config,goal_id,project_id,status,"
            "start_date,note,safety_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (body["title"], st, json.dumps(cfg), body.get("goal_id"), body.get("project_id"),
             body.get("status", "active"), body.get("start_date"), body.get("note"),
             body.get("safety_note"), now, now))
        hid = cur.lastrowid
        for i, s in enumerate(body.get("subtasks", [])):
            conn.execute("INSERT INTO habit_subtasks(habit_id,title,sort_order) VALUES(?,?,?)",
                         (hid, s["title"] if isinstance(s, dict) else str(s), i))
        store.audit(conn, actor, "create", "habit", hid, {"title": body["title"]})
        conn.commit()
        h = conn.execute("SELECT * FROM habits WHERE id=?", (hid,)).fetchone()
        return {**dict(h), "subtasks": [dict(s) for s in store.subtasks_of(conn, hid)]}

    def patch_habit(self, conn, hid, body, actor):
        h = conn.execute("SELECT * FROM habits WHERE id=? AND deleted_at IS NULL",
                         (hid,)).fetchone()
        if not h:
            raise ApiError(404, "habit not found")
        fields = {k: v for k, v in body.items() if k in {
            "title", "status", "paused_from", "paused_to", "goal_id", "project_id",
            "start_date", "end_date", "note", "safety_note", "schedule_type"}}
        if "schedule_config" in body:
            fields["schedule_config"] = json.dumps(body["schedule_config"])
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE habits SET {sets}, updated_at=? WHERE id=?",
                         (*fields.values(), store.now_utc(), hid))
            store.audit(conn, actor, "update", "habit", hid, {"changed": list(fields)})
        conn.commit()
        h = conn.execute("SELECT * FROM habits WHERE id=?", (hid,)).fetchone()
        return {**dict(h), "subtasks": [dict(s) for s in store.subtasks_of(conn, hid)]}

    def habit_trend(self, conn, hid, q):
        days = int(q.get("days", 30))
        end = self._resolve_date(conn, q.get("end"))
        return store.habit_consistency(conn, hid, end - timedelta(days=days - 1), end)

    # -- metrics and observations ----------------------------------------------

    VALID_TYPES = {"numeric", "boolean", "categorical", "duration", "count", "rating", "text"}
    VALID_MISSING = {"unknown", "zero", "not_applicable", "incomplete"}

    def list_metrics(self, conn):
        rows = conn.execute("SELECT * FROM metric_defs ORDER BY label").fetchall()
        out = []
        for m in rows:
            n = conn.execute("SELECT COUNT(*) c FROM observations WHERE metric_id=? "
                             "AND deleted_at IS NULL", (m["id"],)).fetchone()["c"]
            out.append({**dict(m), "observations": n,
                        "options": json.loads(m["options"]) if m["options"] else None})
        return {"metrics": out}

    def create_metric(self, conn, body, actor):
        self._require(body, "id", "label", "type")
        if body["type"] not in self.VALID_TYPES:
            raise ApiError(400, f"type must be one of {sorted(self.VALID_TYPES)}")
        ms = body.get("missing_semantics", "unknown")
        if ms not in self.VALID_MISSING:
            raise ApiError(400, "missing_semantics must be one of "
                                f"{sorted(self.VALID_MISSING)} — these are four different "
                                "states and the choice changes every average")
        now = store.now_utc()
        try:
            conn.execute(
                "INSERT INTO metric_defs(id,label,type,unit,options,min_value,max_value,"
                "aggregation,chart,missing_semantics,privacy,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (body["id"], body["label"], body["type"], body.get("unit"),
                 json.dumps(body["options"]) if body.get("options") else None,
                 body.get("min_value"), body.get("max_value"),
                 body.get("aggregation", "mean"), body.get("chart", "line"), ms,
                 body.get("privacy", "private"), now, now))
        except sqlite3.IntegrityError:
            raise ApiError(409, f"metric '{body['id']}' already exists")
        store.audit(conn, actor, "create", "metric", body["id"], {"label": body["label"]})
        conn.commit()
        return dict(conn.execute("SELECT * FROM metric_defs WHERE id=?",
                                 (body["id"],)).fetchone())

    def patch_metric(self, conn, mid, body, actor):
        m = conn.execute("SELECT * FROM metric_defs WHERE id=?", (mid,)).fetchone()
        if not m:
            raise ApiError(404, "metric not found")
        fields = {k: v for k, v in body.items() if k in {
            "label", "unit", "min_value", "max_value", "aggregation", "chart",
            "missing_semantics", "privacy", "active"}}
        if "missing_semantics" in fields and fields["missing_semantics"] not in self.VALID_MISSING:
            raise ApiError(400, "invalid missing_semantics")
        if "options" in body:
            fields["options"] = json.dumps(body["options"])
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE metric_defs SET {sets}, updated_at=? WHERE id=?",
                         (*fields.values(), store.now_utc(), mid))
            store.audit(conn, actor, "update", "metric", mid, {"changed": list(fields)})
        conn.commit()
        return dict(conn.execute("SELECT * FROM metric_defs WHERE id=?", (mid,)).fetchone())

    def metric_series(self, conn, mid, q):
        days = int(q.get("days", 30))
        if days not in (7, 30, 90, 365) and not q.get("start"):
            days = max(1, min(days, 1830))
        end = self._resolve_date(conn, q.get("end"))
        start = store.parse_date(q["start"]) if q.get("start") else end - timedelta(days=days - 1)
        data = store.metric_series(conn, mid, start, end)
        if not data:
            raise ApiError(404, "metric not found")
        return data

    def create_observation(self, conn, body, actor):
        self._require(body, "metric_id")
        m = conn.execute("SELECT * FROM metric_defs WHERE id=?", (body["metric_id"],)).fetchone()
        if not m:
            raise ApiError(404, f"unknown metric '{body['metric_id']}'. define it first — "
                                "an observation without a definition has no units, no range "
                                "and no missing-value meaning")
        d = self._resolve_date(conn, body.get("date"))
        num = text = boolean = None
        v = body.get("value")
        if m["type"] in ("numeric", "duration", "count", "rating"):
            try:
                num = float(v)
            except (TypeError, ValueError):
                raise ApiError(400, f"metric '{m['id']}' is {m['type']}; value must be a number")
            if m["min_value"] is not None and num < m["min_value"]:
                raise ApiError(400, f"value {num} below the defined minimum {m['min_value']}")
            if m["max_value"] is not None and num > m["max_value"]:
                raise ApiError(400, f"value {num} above the defined maximum {m['max_value']}")
        elif m["type"] == "boolean":
            boolean = 1 if v in (True, 1, "true", "yes") else 0
        else:
            text = str(v) if v is not None else None
            if m["options"]:
                opts = json.loads(m["options"])
                if text not in opts:
                    raise ApiError(400, f"value must be one of {opts}")
        estimated = 1 if body.get("estimated") else 0
        if estimated and not body.get("assumption"):
            raise ApiError(400, "an estimated value must carry the assumption behind it")
        cur = conn.execute(
            "INSERT INTO observations(metric_id,date,value_num,value_text,value_bool,unit,note,"
            "estimated,assumption,source,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (m["id"], d.strftime(store.ISO), num, text, boolean, body.get("unit") or m["unit"],
             body.get("note"), estimated, body.get("assumption"), body.get("source"),
             store.now_utc()))
        store.audit(conn, actor, "create", "observation", cur.lastrowid,
                    {"metric_id": m["id"], "date": d.strftime(store.ISO),
                     "estimated": bool(estimated)})
        conn.commit()
        row = dict(conn.execute("SELECT * FROM observations WHERE id=?",
                                (cur.lastrowid,)).fetchone())
        end = d
        row["aggregate_30d"] = store.metric_series(
            conn, m["id"], end - timedelta(days=29), end)["aggregate"]
        return row

    def patch_observation(self, conn, oid, body, actor):
        o = conn.execute("SELECT * FROM observations WHERE id=? AND deleted_at IS NULL",
                         (oid,)).fetchone()
        if not o:
            raise ApiError(404, "observation not found")
        fields = {k: v for k, v in body.items() if k in {
            "date", "value_num", "value_text", "value_bool", "unit", "note", "estimated",
            "assumption", "source"}}
        if "value" in body:
            m = conn.execute("SELECT * FROM metric_defs WHERE id=?", (o["metric_id"],)).fetchone()
            if m["type"] in ("numeric", "duration", "count", "rating"):
                fields["value_num"] = float(body["value"])
            elif m["type"] == "boolean":
                fields["value_bool"] = 1 if body["value"] in (True, 1, "true", "yes") else 0
            else:
                fields["value_text"] = str(body["value"])
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE observations SET {sets} WHERE id=?", (*fields.values(), oid))
            store.audit(conn, actor, "correct", "observation", oid,
                        {"changed": list(fields), "previous": {
                            "value_num": o["value_num"], "value_text": o["value_text"],
                            "value_bool": o["value_bool"], "date": o["date"]}})
        conn.commit()
        return dict(conn.execute("SELECT * FROM observations WHERE id=?", (oid,)).fetchone())

    def delete_observation(self, conn, oid, actor):
        o = conn.execute("SELECT * FROM observations WHERE id=? AND deleted_at IS NULL",
                         (oid,)).fetchone()
        if not o:
            raise ApiError(404, "observation not found — read before deleting, never guess an id")
        conn.execute("UPDATE observations SET deleted_at=? WHERE id=?", (store.now_utc(), oid))
        store.audit(conn, actor, "delete", "observation", oid,
                    {"metric_id": o["metric_id"], "date": o["date"],
                     "value_num": o["value_num"], "value_text": o["value_text"]})
        conn.commit()
        return {"deleted": oid, "note": "soft delete; the value is preserved in the audit log"}

    def list_observations(self, conn, q):
        sql = "SELECT * FROM observations WHERE deleted_at IS NULL"
        args = []
        if q.get("metric_id"):
            sql += " AND metric_id=?"
            args.append(q["metric_id"])
        if q.get("date"):
            sql += " AND date=?"
            args.append(q["date"])
        sql += " ORDER BY date DESC, id DESC LIMIT ?"
        args.append(int(q.get("limit", 100)))
        return {"observations": [dict(r) for r in conn.execute(sql, args).fetchall()]}

    # -- events, links, data ----------------------------------------------------

    def create_event(self, conn, body, actor):
        self._require(body, "title")
        d = self._resolve_date(conn, body.get("date"))
        cur = conn.execute(
            "INSERT INTO life_events(date,title,category,detail,kb_path,recorded_at) "
            "VALUES(?,?,?,?,?,?)",
            (d.strftime(store.ISO), body["title"], body.get("category"), body.get("detail"),
             body.get("kb_path"), store.now_utc()))
        store.audit(conn, actor, "create", "event", cur.lastrowid, {"title": body["title"]})
        conn.commit()
        return dict(conn.execute("SELECT * FROM life_events WHERE id=?",
                                 (cur.lastrowid,)).fetchone())

    def create_link(self, conn, body, actor):
        self._require(body, "from_type", "from_id", "to_type", "to_id")
        conn.execute("INSERT OR IGNORE INTO links(from_type,from_id,to_type,to_id,relation) "
                     "VALUES(?,?,?,?,?)",
                     (body["from_type"], str(body["from_id"]), body["to_type"],
                      str(body["to_id"]), body.get("relation", "supports")))
        store.audit(conn, actor, "create", "link", None, dict(body))
        conn.commit()
        return {"ok": True}

    def data_summary(self, conn, q):
        days = int(q.get("days", 30))
        end = self._resolve_date(conn, q.get("end"))
        start = end - timedelta(days=days - 1)

        goals = conn.execute("SELECT * FROM goals WHERE deleted_at IS NULL AND status IN "
                             "('active','blocked')").fetchall()
        projects = conn.execute("SELECT * FROM projects WHERE deleted_at IS NULL AND "
                                "status='active'").fetchall()
        habits = conn.execute("SELECT * FROM habits WHERE deleted_at IS NULL AND "
                              "status='active'").fetchall()
        metrics = conn.execute("SELECT * FROM metric_defs WHERE active=1 ORDER BY label").fetchall()

        return {
            "range": {"start": start.strftime(store.ISO), "end": end.strftime(store.ISO),
                      "days": days},
            "goals": [{"id": g["id"], "title": g["title"], "status": g["status"],
                       "next_review": g["next_review"],
                       "progress": store.goal_progress(conn, g["id"])} for g in goals],
            "projects": [{"id": p["id"], "title": p["title"], "phase": p["phase"],
                          "progress": store.project_progress(conn, p["id"]),
                          "health": store.project_health(conn, p)} for p in projects],
            "habits": [store.habit_consistency(conn, h["id"], start, end) for h in habits],
            "metrics": [{"id": m["id"], "label": m["label"], "type": m["type"],
                         "chart": m["chart"], "unit": m["unit"]} for m in metrics],
        }

    def audit_log(self, conn, q):
        rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?",
                            (int(q.get("limit", 50)),)).fetchall()
        return {"audit": [dict(r) for r in rows]}


# ------------------------------------------------------------------------ routing

ROUTES = [
    ("POST", r"^/api/session$", "session"),
    ("DELETE", r"^/api/session$", "session"),
    ("GET", r"^/api/settings$", "settings_get"),
    ("PATCH", r"^/api/settings$", "settings_patch"),
    ("GET", r"^/api/today$", "today"),
    ("GET", r"^/api/habits$", "habits_list"),
    ("POST", r"^/api/habits$", "habits_create"),
    ("PATCH", r"^/api/habits/(\d+)$", "habit_patch"),
    ("GET", r"^/api/habits/(\d+)/trend$", "habit_trend"),
    ("POST", r"^/api/habits/(\d+)/complete$", "habit_complete"),
    ("POST", r"^/api/habits/(\d+)/reopen$", "habit_reopen"),
    ("GET", r"^/api/goals$", "goals_list"),
    ("POST", r"^/api/goals$", "goals_create"),
    ("GET", r"^/api/goals/(\d+)$", "goal_get"),
    ("PATCH", r"^/api/goals/(\d+)$", "goal_patch"),
    ("POST", r"^/api/goals/(\d+)/criteria$", "criterion_add"),
    ("PATCH", r"^/api/criteria/(\d+)$", "criterion_patch"),
    ("POST", r"^/api/milestones$", "milestone_add"),
    ("PATCH", r"^/api/milestones/(\d+)$", "milestone_patch"),
    ("GET", r"^/api/projects$", "projects_list"),
    ("POST", r"^/api/projects$", "projects_create"),
    ("PATCH", r"^/api/projects/(\d+)$", "project_patch"),
    ("POST", r"^/api/tasks$", "task_create"),
    ("PATCH", r"^/api/tasks/(\d+)$", "task_patch"),
    ("POST", r"^/api/tasks/(\d+)/complete$", "task_complete"),
    ("POST", r"^/api/tasks/(\d+)/reopen$", "task_reopen"),
    ("GET", r"^/api/metrics$", "metrics_list"),
    ("POST", r"^/api/metrics$", "metric_create"),
    ("PATCH", r"^/api/metrics/([\w.-]+)$", "metric_patch"),
    ("GET", r"^/api/metrics/([\w.-]+)/series$", "metric_series"),
    ("GET", r"^/api/observations$", "observations_list"),
    ("POST", r"^/api/observations$", "observation_create"),
    ("PATCH", r"^/api/observations/(\d+)$", "observation_patch"),
    ("DELETE", r"^/api/observations/(\d+)$", "observation_delete"),
    ("POST", r"^/api/events$", "event_create"),
    ("POST", r"^/api/links$", "link_create"),
    ("GET", r"^/api/data/summary$", "data_summary"),
    ("GET", r"^/api/audit$", "audit_log"),
]
COMPILED = [(m, re.compile(p), name) for m, p, name in ROUTES]


class Handler(BaseHTTPRequestHandler):
    server_version = "life-tracker"
    protocol_version = "HTTP/1.1"
    # bound per server by serve(), never on this base class — two servers in one process
    # must not share an app, or the second one silently steals the first one's database.
    app: Tracker = None

    def log_message(self, fmt, *args):
        # method, path and status only. never query strings, bodies, cookies or tokens.
        if os.environ.get("LIFE_TRACKER_QUIET"):
            return
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # -- plumbing ---------------------------------------------------------------

    def _send(self, status, payload, extra_headers=None):
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            raise ApiError(400, "body must be json")

    def _query(self):
        from urllib.parse import parse_qs, urlparse

        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _actor(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            if hmac.compare_digest(auth[7:].strip(), self.app.token):
                return "agent"
            raise ApiError(401, "invalid bearer token")
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        sid = cookie["lt_session"].value if "lt_session" in cookie else None
        if sid and self.app.session_valid(sid):
            return "web"
        return None

    # -- dispatch ---------------------------------------------------------------

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method):
        from urllib.parse import urlparse

        path = urlparse(self.path).path
        try:
            if not path.startswith("/api/"):
                return self._serve_static(path)
            if path == "/api/health":
                return self._send(200, {"ok": True, "service": "life-tracker"})

            route = None
            for m, rx, name in COMPILED:
                mt = rx.match(path)
                if mt and m == method:
                    route = (name, mt.groups())
                    break
            if not route:
                allowed = {m for m, rx, _ in COMPILED if rx.match(path)}
                if allowed:
                    raise ApiError(405, f"method not allowed; try {sorted(allowed)}")
                raise ApiError(404, "no such endpoint")

            name, args = route
            actor = self._actor()
            extra = {}

            if name == "session" and method == "POST":
                body = self._read_body()
                payload, sid = self.app.new_session(body)
                extra["Set-Cookie"] = (f"lt_session={sid}; HttpOnly; SameSite=Strict; "
                                       f"Path=/; Max-Age={SESSION_TTL_SECONDS}")
                return self._send(200, payload, extra)
            if name == "session" and method == "DELETE":
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                if "lt_session" in cookie:
                    self.app.sessions.pop(cookie["lt_session"].value, None)
                extra["Set-Cookie"] = "lt_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
                return self._send(200, {"ok": True}, extra)

            if actor is None:
                raise ApiError(401, "authentication required")

            if method != "GET":
                if actor == "web":
                    if (method, name) not in WEB_WRITABLE:
                        raise ApiError(
                            403,
                            "the web app can complete and reopen habits and tasks; "
                            "everything else — goals, projects, metric definitions, "
                            "observations, corrections — is written by the agent. "
                            "the dashboard is read-only by design.")
                    if self.headers.get("X-Requested-With") != "life-tracker":
                        raise ApiError(403, "missing X-Requested-With header")

            conn = self.app._conn()
            try:
                result = self._call(name, args, method, conn, actor)
            finally:
                conn.close()
            return self._send(200, result)

        except ApiError as e:
            return self._send(e.status, e.payload)
        except BrokenPipeError:
            return
        except Exception as e:  # never leak internals to the client
            sys.stderr.write(f"internal error on {method} {path}: {type(e).__name__}\n")
            return self._send(500, {"error": "internal error", "type": type(e).__name__})

    def _call(self, name, args, method, conn, actor):
        app, q = self.app, self._query()
        body = self._read_body() if method in ("POST", "PATCH") else {}

        if name == "settings_get":
            return app.get_settings(conn)
        if name == "settings_patch":
            return app.patch_settings(conn, body, actor)
        if name == "today":
            return app.today(conn, q)
        if name == "habits_list":
            return app.list_habits(conn)
        if name == "habits_create":
            return app.create_habit(conn, body, actor)
        if name == "habit_patch":
            return app.patch_habit(conn, int(args[0]), body, actor)
        if name == "habit_trend":
            return app.habit_trend(conn, int(args[0]), q)
        if name == "habit_complete":
            return app.habit_complete(conn, int(args[0]), body, actor)
        if name == "habit_reopen":
            return app.habit_reopen(conn, int(args[0]), body, actor)
        if name == "goals_list":
            return app.list_goals(conn)
        if name == "goals_create":
            return app.create_goal(conn, body, actor)
        if name == "goal_get":
            return app.get_goal(conn, int(args[0]))
        if name == "goal_patch":
            return app.patch_goal(conn, int(args[0]), body, actor)
        if name == "criterion_add":
            return app.add_criterion(conn, int(args[0]), body, actor)
        if name == "criterion_patch":
            return app.patch_criterion(conn, int(args[0]), body, actor)
        if name == "milestone_add":
            return app.add_milestone(conn, body, actor)
        if name == "milestone_patch":
            return app.patch_milestone(conn, int(args[0]), body, actor)
        if name == "projects_list":
            return app.list_projects(conn)
        if name == "projects_create":
            return app.create_project(conn, body, actor)
        if name == "project_patch":
            return app.patch_project(conn, int(args[0]), body, actor)
        if name == "task_create":
            return app.create_task(conn, body, actor)
        if name == "task_patch":
            return app.patch_task(conn, int(args[0]), body, actor)
        if name == "task_complete":
            return app.task_set_status(conn, int(args[0]), True, body, actor)
        if name == "task_reopen":
            return app.task_set_status(conn, int(args[0]), False, body, actor)
        if name == "metrics_list":
            return app.list_metrics(conn)
        if name == "metric_create":
            return app.create_metric(conn, body, actor)
        if name == "metric_patch":
            return app.patch_metric(conn, args[0], body, actor)
        if name == "metric_series":
            return app.metric_series(conn, args[0], q)
        if name == "observations_list":
            return app.list_observations(conn, q)
        if name == "observation_create":
            return app.create_observation(conn, body, actor)
        if name == "observation_patch":
            return app.patch_observation(conn, int(args[0]), body, actor)
        if name == "observation_delete":
            return app.delete_observation(conn, int(args[0]), actor)
        if name == "event_create":
            return app.create_event(conn, body, actor)
        if name == "link_create":
            return app.create_link(conn, body, actor)
        if name == "data_summary":
            return app.data_summary(conn, q)
        if name == "audit_log":
            return app.audit_log(conn, q)
        raise ApiError(500, f"unrouted: {name}")

    # -- static -----------------------------------------------------------------

    def _serve_static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            return self._send(404, {"error": "not found"})
        data = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)


def serve(host="127.0.0.1", port=8787, db_path=None, token=None):
    db_path = db_path or str(HERE / "life_tracker.db")
    app = Tracker(db_path, token or load_token())
    bound = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((host, port), bound)
    return httpd, app


def main():
    ap = argparse.ArgumentParser(description="private life tracker")
    ap.add_argument("--host", default="127.0.0.1",
                    help="default 127.0.0.1; this is personal data, keep it local")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--db", default=str(HERE / "life_tracker.db"))
    args = ap.parse_args()

    token = load_token()
    httpd, app = serve(args.host, args.port, args.db, token)
    print(f"life tracker on http://{args.host}:{args.port}  (db: {args.db})")
    print(f"token file: {HERE / '.token'}  — paste its contents into the web app to sign in")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("warning: binding beyond localhost exposes personal data on the network")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
