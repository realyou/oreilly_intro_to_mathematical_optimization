"""storage and semantics for the life tracker.

sqlite + stdlib only. this module owns the rules that decide what a number means:
what counts as a scheduled day, what counts as missing, and where progress comes from.
the http layer in server.py does routing and auth and nothing else.

the rules encoded here, once, so no caller can get them wrong:

- a completion exists only because someone explicitly recorded it.
- unknown, zero, not_applicable and incomplete are four different states.
- habit consistency divides by scheduled days, and paused or skipped days are not
  scheduled days.
- goal progress comes from success criteria or milestones, never task volume.
- project progress comes from explicit milestones or task scope, never elapsed time.
- nothing is destroyed; deletions are soft and corrections keep their history.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date as Date
from datetime import datetime, timedelta, timezone

ISO = "%Y-%m-%d"

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS life_areas (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id                INTEGER PRIMARY KEY,
    area_id           INTEGER REFERENCES life_areas(id),
    title             TEXT NOT NULL,
    outcome           TEXT,
    definition_of_done TEXT,
    rationale         TEXT,
    baseline          TEXT,
    status            TEXT NOT NULL DEFAULT 'not_started',
    status_reason     TEXT,
    target_date       TEXT,
    next_review       TEXT,
    kb_path           TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    deleted_at        TEXT
);

CREATE TABLE IF NOT EXISTS success_criteria (
    id          INTEGER PRIMARY KEY,
    goal_id     INTEGER NOT NULL REFERENCES goals(id),
    description TEXT NOT NULL,
    metric_id   TEXT REFERENCES metric_defs(id),
    target_value REAL,
    comparator  TEXT,
    met         INTEGER NOT NULL DEFAULT 0,
    met_at      TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS milestones (
    id           INTEGER PRIMARY KEY,
    goal_id      INTEGER REFERENCES goals(id),
    project_id   INTEGER REFERENCES projects(id),
    title        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open',
    target_date  TEXT,
    completed_at TEXT,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    deleted_at   TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY,
    goal_id     INTEGER REFERENCES goals(id),
    title       TEXT NOT NULL,
    purpose     TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    status_reason TEXT,
    phase       TEXT,
    owner       TEXT,
    deadline    TEXT,
    blocker     TEXT,
    kb_path     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY,
    project_id   INTEGER REFERENCES projects(id),
    goal_id      INTEGER REFERENCES goals(id),
    milestone_id INTEGER REFERENCES milestones(id),
    parent_id    INTEGER REFERENCES tasks(id),
    title        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open',
    blocked_reason TEXT,
    due_date     TEXT,
    completed_at TEXT,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    deleted_at   TEXT
);

CREATE TABLE IF NOT EXISTS habits (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    schedule_config TEXT NOT NULL DEFAULT '{}',
    goal_id       INTEGER REFERENCES goals(id),
    project_id    INTEGER REFERENCES projects(id),
    status        TEXT NOT NULL DEFAULT 'active',
    paused_from   TEXT,
    paused_to     TEXT,
    start_date    TEXT,
    end_date      TEXT,
    note          TEXT,
    safety_note   TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    deleted_at    TEXT
);

CREATE TABLE IF NOT EXISTS habit_subtasks (
    id         INTEGER PRIMARY KEY,
    habit_id   INTEGER NOT NULL REFERENCES habits(id),
    title      TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT
);

-- subtask_id 0 means the parent habit itself.
CREATE TABLE IF NOT EXISTS habit_completions (
    id          INTEGER PRIMARY KEY,
    habit_id    INTEGER NOT NULL REFERENCES habits(id),
    subtask_id  INTEGER NOT NULL DEFAULT 0,
    date        TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'completed',
    note        TEXT,
    recorded_at TEXT NOT NULL,
    UNIQUE (habit_id, subtask_id, date)
);

CREATE TABLE IF NOT EXISTS metric_defs (
    id            TEXT PRIMARY KEY,
    label         TEXT NOT NULL,
    type          TEXT NOT NULL,
    unit          TEXT,
    options       TEXT,
    min_value     REAL,
    max_value     REAL,
    aggregation   TEXT NOT NULL DEFAULT 'mean',
    chart         TEXT NOT NULL DEFAULT 'line',
    missing_semantics TEXT NOT NULL DEFAULT 'unknown',
    privacy       TEXT NOT NULL DEFAULT 'private',
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    id          INTEGER PRIMARY KEY,
    metric_id   TEXT NOT NULL REFERENCES metric_defs(id),
    date        TEXT NOT NULL,
    value_num   REAL,
    value_text  TEXT,
    value_bool  INTEGER,
    unit        TEXT,
    note        TEXT,
    estimated   INTEGER NOT NULL DEFAULT 0,
    assumption  TEXT,
    source      TEXT,
    recorded_at TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS life_events (
    id          INTEGER PRIMARY KEY,
    date        TEXT NOT NULL,
    title       TEXT NOT NULL,
    category    TEXT,
    detail      TEXT,
    kb_path     TEXT,
    recorded_at TEXT NOT NULL,
    deleted_at  TEXT
);

CREATE TABLE IF NOT EXISTS links (
    id        INTEGER PRIMARY KEY,
    from_type TEXT NOT NULL,
    from_id   TEXT NOT NULL,
    to_type   TEXT NOT NULL,
    to_id     TEXT NOT NULL,
    relation  TEXT NOT NULL DEFAULT 'supports',
    UNIQUE (from_type, from_id, to_type, to_id, relation)
);

-- append-only. corrections and deletions are recorded, never erased.
CREATE TABLE IF NOT EXISTS audit (
    id        INTEGER PRIMARY KEY,
    at        TEXT NOT NULL,
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    entity    TEXT NOT NULL,
    entity_id TEXT,
    detail    TEXT
);

CREATE INDEX IF NOT EXISTS idx_obs_metric_date ON observations(metric_id, date);
CREATE INDEX IF NOT EXISTS idx_completions_date ON habit_completions(date);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
"""


# --------------------------------------------------------------------------- utils

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_date(s: str) -> Date:
    return datetime.strptime(s, ISO).date()


def daterange(start: Date, end: Date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def audit(conn, actor, action, entity, entity_id=None, detail=None):
    conn.execute(
        "INSERT INTO audit(at,actor,action,entity,entity_id,detail) VALUES(?,?,?,?,?,?)",
        (now_utc(), actor, action, entity, str(entity_id) if entity_id is not None else None,
         json.dumps(detail) if detail is not None else None),
    )


def today_in_tz(conn) -> str | None:
    """today in the user's timezone, or None if the timezone was never configured.

    returning None is deliberate. guessing utc would silently file a completion on the
    wrong day, which is exactly the kind of quiet fabrication this system exists to avoid.
    """
    tz = get_setting(conn, "timezone")
    if not tz:
        return None
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz)).date().strftime(ISO)
    except Exception:
        return None


# ------------------------------------------------------------------- habit schedule

def schedule_config(habit) -> dict:
    try:
        return json.loads(habit["schedule_config"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def is_paused_on(habit, d: Date) -> bool:
    if habit["status"] in ("paused", "archived"):
        return True
    pf, pt = habit["paused_from"], habit["paused_to"]
    if pf and d >= parse_date(pf):
        if not pt or d <= parse_date(pt):
            return True
    return False


def is_scheduled(habit, d: Date) -> bool:
    """is this habit due on this date?

    a day that is not scheduled is not a missed day. min_frequency habits have no
    specific due days at all — they are measured against their period, so they never
    contribute a missed day to a daily denominator.
    """
    if habit["deleted_at"] or is_paused_on(habit, d):
        return False
    if habit["start_date"] and d < parse_date(habit["start_date"]):
        return False
    if habit["end_date"] and d > parse_date(habit["end_date"]):
        return False

    kind = habit["schedule_type"]
    cfg = schedule_config(habit)

    if kind == "daily":
        return True
    if kind == "weekdays":
        return d.weekday() in cfg.get("days", [])
    if kind == "interval":
        every = int(cfg.get("every_n_days", 1)) or 1
        anchor_s = cfg.get("anchor") or habit["start_date"] or habit["created_at"][:10]
        return (d - parse_date(anchor_s)).days % every == 0
    if kind in ("min_frequency", "weekly"):
        return False
    return False


def period_bounds(d: Date, period: str) -> tuple[Date, Date]:
    if period == "month":
        start = d.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, nxt - timedelta(days=1)
    start = d - timedelta(days=d.weekday())  # monday
    return start, start + timedelta(days=6)


def completion_map(conn, habit_id: int, start: Date, end: Date) -> dict:
    rows = conn.execute(
        "SELECT date, subtask_id, state FROM habit_completions "
        "WHERE habit_id=? AND date BETWEEN ? AND ?",
        (habit_id, start.strftime(ISO), end.strftime(ISO)),
    ).fetchall()
    out: dict[str, dict[int, str]] = {}
    for r in rows:
        out.setdefault(r["date"], {})[r["subtask_id"]] = r["state"]
    return out


def subtasks_of(conn, habit_id: int):
    return conn.execute(
        "SELECT * FROM habit_subtasks WHERE habit_id=? AND deleted_at IS NULL "
        "ORDER BY sort_order, id",
        (habit_id,),
    ).fetchall()


def habit_day_state(conn, habit, d: Date, cmap=None) -> dict:
    """what happened with this habit on this day.

    the parent counts as done when it was explicitly ticked, or when every one of its
    subtasks was explicitly ticked — that second case is still a record of explicit user
    actions, not an inference from the clock.
    """
    ds = d.strftime(ISO)
    cmap = cmap if cmap is not None else completion_map(conn, habit["id"], d, d)
    day = cmap.get(ds, {})
    subs = subtasks_of(conn, habit["id"])
    sub_states = {s["id"]: day.get(s["id"]) for s in subs}
    done_subs = sum(1 for v in sub_states.values() if v == "completed")
    parent_state = day.get(0)

    complete = parent_state == "completed"
    if not complete and subs and done_subs == len(subs):
        complete = True

    return {
        "date": ds,
        "scheduled": is_scheduled(habit, d),
        "state": parent_state,
        "complete": complete,
        "skipped": parent_state == "skipped",
        "subtasks": [
            {"id": s["id"], "title": s["title"], "complete": sub_states[s["id"]] == "completed"}
            for s in subs
        ],
        "subtasks_done": done_subs,
        "subtasks_total": len(subs),
    }


def min_frequency_status(conn, habit, d: Date) -> dict | None:
    cfg = schedule_config(habit)
    if habit["schedule_type"] not in ("min_frequency", "weekly"):
        return None
    times = int(cfg.get("times", 1))
    period = cfg.get("period", "week")
    start, end = period_bounds(d, period)
    cmap = completion_map(conn, habit["id"], start, end)
    done = sum(1 for day in cmap.values() if day.get(0) == "completed")
    return {"period": period, "period_start": start.strftime(ISO),
            "period_end": end.strftime(ISO), "target": times, "done": done,
            "remaining": max(0, times - done)}


# ------------------------------------------------------------------------ today view

def today_view(conn, d: Date) -> dict:
    ds = d.strftime(ISO)
    items = []

    habits = conn.execute(
        "SELECT * FROM habits WHERE deleted_at IS NULL AND status != 'archived' ORDER BY id"
    ).fetchall()
    for h in habits:
        freq = min_frequency_status(conn, h, d)
        scheduled = is_scheduled(h, d)
        flexible = freq is not None and freq["remaining"] > 0 and not is_paused_on(h, d)
        state = habit_day_state(conn, h, d)
        if not (scheduled or flexible or state["complete"] or state["state"]):
            continue
        items.append({
            "kind": "habit",
            "id": h["id"],
            "title": h["title"],
            "scheduled": scheduled,
            "flexible": flexible,
            "frequency": freq,
            "goal_id": h["goal_id"],
            "project_id": h["project_id"],
            "supports": _supports_label(conn, h["goal_id"], h["project_id"]),
            "safety_note": h["safety_note"],
            "paused": is_paused_on(h, d),
            **{k: state[k] for k in
               ("state", "complete", "skipped", "subtasks", "subtasks_done", "subtasks_total")},
        })

    tasks = conn.execute(
        "SELECT t.*, p.title AS project_title, g.title AS goal_title "
        "FROM tasks t LEFT JOIN projects p ON p.id=t.project_id "
        "LEFT JOIN goals g ON g.id=t.goal_id "
        "WHERE t.deleted_at IS NULL AND t.parent_id IS NULL "
        "  AND (t.due_date IS NULL OR t.due_date <= ?) "
        "  AND (t.status='open' OR (t.status='done' AND substr(t.completed_at,1,10)=?)) "
        "ORDER BY t.due_date IS NULL, t.due_date, t.sort_order, t.id",
        (ds, ds),
    ).fetchall()
    for t in tasks:
        subs = conn.execute(
            "SELECT id,title,status FROM tasks WHERE parent_id=? AND deleted_at IS NULL "
            "ORDER BY sort_order, id", (t["id"],)
        ).fetchall()
        items.append({
            "kind": "task",
            "id": t["id"],
            "title": t["title"],
            "due_date": t["due_date"],
            "complete": t["status"] == "done",
            "blocked_reason": t["blocked_reason"],
            "goal_id": t["goal_id"],
            "project_id": t["project_id"],
            "supports": t["project_title"] or t["goal_title"],
            "subtasks": [{"id": s["id"], "title": s["title"], "complete": s["status"] == "done"}
                         for s in subs],
            "subtasks_done": sum(1 for s in subs if s["status"] == "done"),
            "subtasks_total": len(subs),
        })

    done = sum(1 for i in items if i["complete"])
    return {
        "date": ds,
        "previous": (d - timedelta(days=1)).strftime(ISO),
        "next": (d + timedelta(days=1)).strftime(ISO),
        "items": items,
        "counts": {"total": len(items), "completed": done, "remaining": len(items) - done},
    }


def _supports_label(conn, goal_id, project_id):
    if project_id:
        r = conn.execute("SELECT title FROM projects WHERE id=?", (project_id,)).fetchone()
        if r:
            return r["title"]
    if goal_id:
        r = conn.execute("SELECT title FROM goals WHERE id=?", (goal_id,)).fetchone()
        if r:
            return r["title"]
    return None


# ------------------------------------------------------------------------- progress

def goal_progress(conn, goal_id: int) -> dict:
    """progress from success criteria, else milestones, else nothing.

    a goal with neither returns basis 'qualitative' and no number. that is a real answer:
    inventing a percentage for a goal nobody defined criteria for is worse than saying so.
    """
    crit = conn.execute(
        "SELECT * FROM success_criteria WHERE goal_id=? AND deleted_at IS NULL "
        "ORDER BY sort_order, id", (goal_id,)
    ).fetchall()
    if crit:
        met = sum(1 for c in crit if c["met"])
        return {"basis": "success_criteria", "met": met, "total": len(crit),
                "fraction": met / len(crit)}
    ms = conn.execute(
        "SELECT * FROM milestones WHERE goal_id=? AND deleted_at IS NULL", (goal_id,)
    ).fetchall()
    if ms:
        done = sum(1 for m in ms if m["status"] == "done")
        return {"basis": "milestones", "met": done, "total": len(ms),
                "fraction": done / len(ms)}
    return {"basis": "qualitative", "met": None, "total": 0, "fraction": None}


def project_progress(conn, project_id: int) -> dict:
    ms = conn.execute(
        "SELECT * FROM milestones WHERE project_id=? AND deleted_at IS NULL", (project_id,)
    ).fetchall()
    if ms:
        done = sum(1 for m in ms if m["status"] == "done")
        return {"basis": "milestones", "met": done, "total": len(ms),
                "fraction": done / len(ms)}
    ts = conn.execute(
        "SELECT * FROM tasks WHERE project_id=? AND deleted_at IS NULL", (project_id,)
    ).fetchall()
    if ts:
        done = sum(1 for t in ts if t["status"] == "done")
        return {"basis": "task_scope", "met": done, "total": len(ts),
                "fraction": done / len(ts)}
    return {"basis": "undefined", "met": None, "total": 0, "fraction": None}


def project_health(conn, project) -> dict:
    """health from explicit rules, with the reason attached. never a mood, never a curve."""
    reasons = []
    if project["status"] in ("paused", "completed", "abandoned"):
        return {"health": project["status"], "reasons": [f"status is {project['status']}"]}
    if project["blocker"]:
        return {"health": "blocked", "reasons": [f"blocker: {project['blocker']}"]}

    nxt = conn.execute(
        "SELECT id FROM tasks WHERE project_id=? AND status='open' AND deleted_at IS NULL "
        "LIMIT 1", (project["id"],)
    ).fetchone()
    if not nxt:
        reasons.append("no open next action")
    if project["deadline"]:
        prog = project_progress(conn, project["id"])
        if prog["fraction"] is not None and prog["fraction"] < 1.0:
            reasons.append(f"deadline {project['deadline']} with "
                           f"{prog['met']}/{prog['total']} {prog['basis']} done")
    return {"health": "needs_attention" if reasons else "on_track", "reasons": reasons}


# -------------------------------------------------------------------------- metrics

def metric_series(conn, metric_id: str, start: Date, end: Date) -> dict:
    m = conn.execute("SELECT * FROM metric_defs WHERE id=?", (metric_id,)).fetchone()
    if not m:
        return {}
    rows = conn.execute(
        "SELECT * FROM observations WHERE metric_id=? AND deleted_at IS NULL "
        "AND date BETWEEN ? AND ? ORDER BY date, id",
        (metric_id, start.strftime(ISO), end.strftime(ISO)),
    ).fetchall()

    points = [{
        "date": r["date"],
        "value": (r["value_num"] if r["value_num"] is not None
                  else (bool(r["value_bool"]) if r["value_bool"] is not None else r["value_text"])),
        "unit": r["unit"] or m["unit"],
        "estimated": bool(r["estimated"]),
        "assumption": r["assumption"],
        "note": r["note"],
        "id": r["id"],
    } for r in rows]

    days_in_range = (end - start).days + 1
    days_with_data = len({p["date"] for p in points})

    numeric = [p["value"] for p in points if isinstance(p["value"], (int, float))
               and not isinstance(p["value"], bool)]
    if m["missing_semantics"] == "zero":
        # absence genuinely means zero for this metric, so missing days join the average.
        numeric = numeric + [0.0] * (days_in_range - days_with_data)

    agg = {"aggregation": m["aggregation"], "value": None, "n": len(numeric)}
    if numeric:
        if m["aggregation"] == "mean":
            agg["value"] = sum(numeric) / len(numeric)
        elif m["aggregation"] == "sum":
            agg["value"] = sum(numeric)
        elif m["aggregation"] == "last":
            agg["value"] = numeric[-1]
        elif m["aggregation"] == "count":
            agg["value"] = len(numeric)
    if m["aggregation"] == "count" and not numeric:
        agg["value"] = len(points)

    distribution = None
    if m["type"] == "categorical" or m["aggregation"] == "distribution":
        distribution = {}
        for p in points:
            distribution[str(p["value"])] = distribution.get(str(p["value"]), 0) + 1

    return {
        "metric": {
            "id": m["id"], "label": m["label"], "type": m["type"], "unit": m["unit"],
            "aggregation": m["aggregation"], "chart": m["chart"],
            "missing_semantics": m["missing_semantics"],
            "options": json.loads(m["options"]) if m["options"] else None,
        },
        "range": {"start": start.strftime(ISO), "end": end.strftime(ISO),
                  "days": days_in_range},
        "points": points,
        "coverage": {
            "observations": len(points),
            "days_with_data": days_with_data,
            "days_in_range": days_in_range,
            "missing_semantics": m["missing_semantics"],
            "note": _coverage_note(m["missing_semantics"]),
        },
        "aggregate": agg,
        "distribution": distribution,
        "estimated_count": sum(1 for p in points if p["estimated"]),
    }


def _coverage_note(sem: str) -> str:
    return {
        "unknown": "days without an observation are unknown and excluded from the average",
        "zero": "days without an observation count as zero for this metric",
        "not_applicable": "days without an observation did not apply and are excluded",
        "incomplete": "partially logged days are excluded from the average but counted here",
    }.get(sem, "")


def habit_consistency(conn, habit_id: int, start: Date, end: Date) -> dict:
    """completion over scheduled days only.

    unscheduled days, paused days and explicitly skipped days are not failures and are
    not in the denominator. streaks are deliberately not returned: a streak punishes one
    missed day and says nothing about recovery, which is the thing worth seeing.
    """
    h = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
    if not h:
        return {}
    cmap = completion_map(conn, habit_id, start, end)
    freq_cfg = schedule_config(h)
    is_freq = h["schedule_type"] in ("min_frequency", "weekly")

    scheduled = completed = skipped = 0
    days = []
    for d in daterange(start, end):
        st = habit_day_state(conn, h, d, cmap)
        if st["skipped"]:
            skipped += 1
            status = "skipped"
        elif st["scheduled"]:
            scheduled += 1
            if st["complete"]:
                completed += 1
            status = "completed" if st["complete"] else "missed"
        elif st["complete"]:
            completed += 1 if is_freq else 0
            status = "completed"
        elif is_paused_on(h, d):
            status = "paused"
        else:
            status = "not_scheduled"
        days.append({"date": d.strftime(ISO), "status": status})

    out = {
        "habit_id": habit_id, "title": h["title"],
        "schedule_type": h["schedule_type"],
        "scheduled_days": scheduled, "completed": completed, "skipped": skipped,
        "consistency": (completed / scheduled) if scheduled else None,
        "days": days,
        "note": "consistency counts scheduled days only; paused and skipped days are excluded",
    }
    if is_freq:
        target = int(freq_cfg.get("times", 1))
        period = freq_cfg.get("period", "week")
        periods = _period_completion(conn, h, start, end, target, period)
        out.update({"consistency": None, "periods": periods,
                    "note": f"minimum-frequency habit: measured per {period}, "
                            f"target {target} per {period}"})
        met = sum(1 for p in periods if p["done"] >= p["target"])
        out["periods_met"] = met
        out["periods_total"] = len(periods)
    return out


def _period_completion(conn, habit, start: Date, end: Date, target: int, period: str):
    seen, out = set(), []
    for d in daterange(start, end):
        ps, pe = period_bounds(d, period)
        if ps in seen:
            continue
        seen.add(ps)
        cmap = completion_map(conn, habit["id"], ps, pe)
        done = sum(1 for day in cmap.values() if day.get(0) == "completed")
        out.append({"period_start": ps.strftime(ISO), "period_end": pe.strftime(ISO),
                    "done": done, "target": target})
    return out
