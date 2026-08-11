"""seed a demo database with FICTIONAL data, so the interface can be seen working.

this exists so nobody has to invent facts about the real user to check that the ui renders.
it refuses to touch the default database, and every row it writes is obviously fictional.

    python3 demo_seed.py --db /tmp/demo.db --today 2026-08-11
    python3 server.py --db /tmp/demo.db --port 8788
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db as store  # noqa: E402

DEFAULT_DB = Path(__file__).resolve().parent / "life_tracker.db"


def seed(db_path: str, today_s: str):
    if Path(db_path).resolve() == DEFAULT_DB.resolve():
        raise SystemExit("refusing to seed demo data into the default database. "
                         "pass --db /tmp/demo.db")
    today = store.parse_date(today_s)
    conn = store.connect(db_path)
    store.init(conn)
    now = store.now_utc()

    store.set_setting(conn, "timezone", "Europe/Berlin")
    store.set_setting(conn, "user_name", "demo (fictional)")

    conn.execute("INSERT OR IGNORE INTO life_areas(name,created_at) VALUES('health',?)", (now,))
    conn.execute("INSERT OR IGNORE INTO life_areas(name,created_at) VALUES('craft',?)", (now,))
    health = conn.execute("SELECT id FROM life_areas WHERE name='health'").fetchone()["id"]
    craft = conn.execute("SELECT id FROM life_areas WHERE name='craft'").fetchone()["id"]

    g1 = conn.execute(
        "INSERT INTO goals(area_id,title,outcome,definition_of_done,rationale,baseline,status,"
        "target_date,next_review,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (health, "[demo] run a 10k", "finish a 10k run without walking",
         "crossed a measured 10k finish line", "wants a concrete endurance target",
         "current longest run: 4 km, as of 2026-07-01", "active",
         (today + timedelta(days=90)).strftime(store.ISO),
         (today + timedelta(days=14)).strftime(store.ISO), now, now)).lastrowid
    for i, (desc, met) in enumerate([("run 10 km without stopping", 0),
                                     ("three consecutive weeks of 3 runs", 1),
                                     ("finish under 60 minutes", 0)]):
        conn.execute("INSERT INTO success_criteria(goal_id,description,met,sort_order) "
                     "VALUES(?,?,?,?)", (g1, desc, met, i))
    for i, (t, st) in enumerate([("run 5 km", "done"), ("run 8 km", "open"),
                                 ("run 10 km", "open")]):
        conn.execute("INSERT INTO milestones(goal_id,title,status,sort_order) VALUES(?,?,?,?)",
                     (g1, t, st, i))

    g2 = conn.execute(
        "INSERT INTO goals(area_id,title,outcome,definition_of_done,status,next_review,"
        "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (craft, "[demo] publish the woodworking site", "a live site with five projects on it",
         "site reachable and five projects written up", "active",
         (today + timedelta(days=7)).strftime(store.ISO), now, now)).lastrowid

    p1 = conn.execute(
        "INSERT INTO projects(goal_id,title,purpose,status,phase,owner,deadline,created_at,"
        "updated_at,kb_path) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (g2, "[demo] build the site", "somewhere to put the work", "active", "build",
         "me", (today + timedelta(days=21)).strftime(store.ISO), now, now,
         "life-knowledge-base/50-projects/projects/prj-demo-site.md")).lastrowid
    for i, (t, st) in enumerate([("pick a static generator", "done"),
                                 ("write the first project page", "open"),
                                 ("photograph the bench", "open")]):
        conn.execute("INSERT INTO tasks(project_id,title,status,completed_at,sort_order) "
                     "VALUES(?,?,?,?,?)",
                     (p1, t, st, today.strftime(store.ISO) if st == "done" else None, i))
    conn.execute("INSERT INTO milestones(project_id,title,status,sort_order) VALUES(?,?,?,?)",
                 (p1, "first page live", "open", 0))

    p2 = conn.execute(
        "INSERT INTO projects(title,purpose,status,phase,blocker,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?)",
        ("[demo] rewire the workshop", "more outlets, fewer extension leads", "active",
         "waiting", "electrician has not confirmed a date", now, now)).lastrowid

    h1 = conn.execute(
        "INSERT INTO habits(title,schedule_type,schedule_config,goal_id,status,created_at,"
        "updated_at) VALUES(?,?,?,?,?,?,?)",
        ("[demo] morning run", "weekdays", json.dumps({"days": [0, 2, 4]}), g1, "active",
         now, now)).lastrowid
    for i, t in enumerate(["warm up", "run", "stretch"]):
        conn.execute("INSERT INTO habit_subtasks(habit_id,title,sort_order) VALUES(?,?,?)",
                     (h1, t, i))
    h2 = conn.execute(
        "INSERT INTO habits(title,schedule_type,schedule_config,status,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?)",
        ("[demo] strength session", "min_frequency", json.dumps({"times": 2, "period": "week"}),
         "active", now, now)).lastrowid
    h3 = conn.execute(
        "INSERT INTO habits(title,schedule_type,schedule_config,status,paused_from,created_at,"
        "updated_at,note) VALUES(?,?,?,?,?,?,?,?)",
        ("[demo] evening reading", "daily", "{}", "paused",
         (today - timedelta(days=10)).strftime(store.ISO), now, now,
         "paused deliberately — paused days are not misses")).lastrowid

    # completions: enough history to make the charts meaningful, with gaps left as gaps.
    # some scheduled days are genuinely missed and one is explicitly skipped, so the
    # difference between "missed" and "skipped" is visible rather than just asserted.
    missed = {4, 18, 25}
    skipped = {11}
    for i in range(60):
        d = today - timedelta(days=i)
        ds = d.strftime(store.ISO)
        if d.weekday() in (0, 2, 4):
            if i in skipped:
                conn.execute("INSERT OR IGNORE INTO habit_completions(habit_id,subtask_id,"
                             "date,state,note,recorded_at) "
                             "VALUES(?,0,?,'skipped',?,?)",
                             (h1, ds, "rest day, agreed in advance", now))
            elif i not in missed:
                conn.execute("INSERT OR IGNORE INTO habit_completions(habit_id,subtask_id,"
                             "date,state,recorded_at) VALUES(?,0,?,'completed',?)",
                             (h1, ds, now))
        if d.weekday() in (1, 5) and i % 5 != 0:
            conn.execute("INSERT OR IGNORE INTO habit_completions(habit_id,subtask_id,date,"
                         "state,recorded_at) VALUES(?,0,?,'completed',?)", (h2, ds, now))

    metrics = [
        ("weight", "[demo] weight", "numeric", "kg", "mean", "line", "unknown", 30, 300),
        ("sleep_hours", "[demo] sleep", "duration", "hours", "mean", "bar", "unknown", 0, 24),
        ("mood", "[demo] mood", "rating", "1-5", "mean", "line", "unknown", 1, 5),
        ("meds_taken", "[demo] medication taken", "boolean", None, "count", "calendar",
         "unknown", None, None),
        ("focus_block", "[demo] deep work blocks", "count", "blocks", "sum", "bar", "zero",
         0, 20),
    ]
    for mid, label, typ, unit, agg, chart, miss, lo, hi in metrics:
        conn.execute(
            "INSERT OR IGNORE INTO metric_defs(id,label,type,unit,aggregation,chart,"
            "missing_semantics,min_value,max_value,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (mid, label, typ, unit, agg, chart, miss, lo, hi, now, now))

    for i in range(60):
        d = today - timedelta(days=i)
        ds = d.strftime(store.ISO)
        if i % 3 == 0:  # weighed intermittently on purpose — missing days stay missing
            conn.execute("INSERT INTO observations(metric_id,date,value_num,unit,recorded_at) "
                         "VALUES('weight',?,?, 'kg',?)", (ds, 78.5 - i * 0.02, now))
        if i % 7 != 5:
            est = 1 if i % 11 == 0 else 0
            conn.execute("INSERT INTO observations(metric_id,date,value_num,unit,estimated,"
                         "assumption,recorded_at) VALUES('sleep_hours',?,?,'hours',?,?,?)",
                         (ds, 6.2 + (i % 5) * 0.4, est,
                          "user said 'about seven hours'" if est else None, now))
        if i % 2 == 0:
            conn.execute("INSERT INTO observations(metric_id,date,value_num,recorded_at) "
                         "VALUES('mood',?,?,?)", (ds, 3 + (i % 3), now))
        if i % 4 != 3:
            conn.execute("INSERT INTO observations(metric_id,date,value_bool,recorded_at) "
                         "VALUES('meds_taken',?,1,?)", (ds, now))
        if i % 3 != 2:
            conn.execute("INSERT INTO observations(metric_id,date,value_num,recorded_at) "
                         "VALUES('focus_block',?,?,?)", (ds, (i % 4), now))

    store.audit(conn, "demo_seed", "seed", "database", None, {"fictional": True})
    conn.commit()

    print(f"seeded fictional demo data into {db_path}")
    print(f"  goals: 2   projects: 2   habits: 3   metrics: {len(metrics)}")
    print("  every row is prefixed [demo] and none of it describes a real person.")
    print(f"\n  python3 server.py --db {db_path} --port 8788")
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="a scratch path, not the real database")
    ap.add_argument("--today", default=None, help="anchor date, YYYY-MM-DD")
    a = ap.parse_args()
    anchor = a.today
    if not anchor:
        from datetime import date as _d

        anchor = _d.today().strftime(store.ISO)
    seed(a.db, anchor)
