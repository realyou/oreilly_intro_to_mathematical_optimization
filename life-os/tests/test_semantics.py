"""the rules that make the numbers honest, tested directly against db.py.

if one of these fails, the tracker is lying to the user about their own life — which is worse
than not tracking at all. these are the assertions the whole system rests on.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tracker"))
import db as store  # noqa: E402

D = store.parse_date


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(str(Path(self.tmp.name) / "t.db"))
        store.init(self.conn)
        self.now = store.now_utc()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def habit(self, title="h", schedule="daily", config=None, **kw):
        cur = self.conn.execute(
            "INSERT INTO habits(title,schedule_type,schedule_config,status,paused_from,"
            "paused_to,start_date,end_date,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (title, schedule, json.dumps(config or {}), kw.get("status", "active"),
             kw.get("paused_from"), kw.get("paused_to"), kw.get("start_date"),
             kw.get("end_date"), self.now, self.now))
        self.conn.commit()
        return self.conn.execute("SELECT * FROM habits WHERE id=?",
                                 (cur.lastrowid,)).fetchone()

    def complete(self, habit_id, date, subtask_id=0, state="completed"):
        self.conn.execute(
            "INSERT OR REPLACE INTO habit_completions(habit_id,subtask_id,date,state,"
            "recorded_at) VALUES(?,?,?,?,?)", (habit_id, subtask_id, date, state, self.now))
        self.conn.commit()

    def metric(self, mid, mtype="numeric", agg="mean", missing="unknown", **kw):
        self.conn.execute(
            "INSERT INTO metric_defs(id,label,type,unit,aggregation,chart,missing_semantics,"
            "min_value,max_value,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (mid, mid, mtype, kw.get("unit"), agg, kw.get("chart", "line"), missing,
             kw.get("min_value"), kw.get("max_value"), self.now, self.now))
        self.conn.commit()

    def observe(self, mid, date, value=None, **kw):
        self.conn.execute(
            "INSERT INTO observations(metric_id,date,value_num,value_text,value_bool,"
            "estimated,assumption,recorded_at) VALUES(?,?,?,?,?,?,?,?)",
            (mid, date, value if isinstance(value, (int, float)) else None,
             kw.get("text"), kw.get("boolean"), 1 if kw.get("estimated") else 0,
             kw.get("assumption"), self.now))
        self.conn.commit()


class HabitScheduling(Base):
    def test_weekdays_only_on_configured_days(self):
        h = self.habit(schedule="weekdays", config={"days": [0, 2, 4]})
        self.assertTrue(store.is_scheduled(h, D("2026-08-10")))    # monday
        self.assertFalse(store.is_scheduled(h, D("2026-08-11")))   # tuesday
        self.assertTrue(store.is_scheduled(h, D("2026-08-12")))    # wednesday

    def test_interval_counts_from_the_anchor(self):
        h = self.habit(schedule="interval",
                       config={"every_n_days": 3, "anchor": "2026-08-01"})
        for d, want in [("2026-08-01", True), ("2026-08-02", False), ("2026-08-04", True),
                        ("2026-08-07", True), ("2026-08-08", False)]:
            self.assertEqual(store.is_scheduled(h, D(d)), want, d)

    def test_min_frequency_has_no_scheduled_days(self):
        """a 3-times-a-week habit must never make tuesday a missed day."""
        h = self.habit(schedule="min_frequency", config={"times": 3, "period": "week"})
        for i in range(7):
            self.assertFalse(store.is_scheduled(h, D("2026-08-10") + timedelta(days=i)))

    def test_paused_days_are_not_scheduled(self):
        h = self.habit(paused_from="2026-08-05", paused_to="2026-08-09")
        self.assertTrue(store.is_scheduled(h, D("2026-08-04")))
        self.assertFalse(store.is_scheduled(h, D("2026-08-07")))
        self.assertTrue(store.is_scheduled(h, D("2026-08-10")))

    def test_open_ended_pause_and_paused_status(self):
        self.assertFalse(store.is_scheduled(self.habit(paused_from="2026-08-05"),
                                            D("2026-12-01")))
        self.assertFalse(store.is_scheduled(self.habit(status="paused"), D("2026-08-05")))

    def test_start_and_end_dates_bound_the_schedule(self):
        h = self.habit(start_date="2026-08-05", end_date="2026-08-07")
        self.assertFalse(store.is_scheduled(h, D("2026-08-04")))
        self.assertTrue(store.is_scheduled(h, D("2026-08-06")))
        self.assertFalse(store.is_scheduled(h, D("2026-08-08")))


class Completion(Base):
    def test_nothing_completes_without_a_record(self):
        """time passing is not evidence. an unrecorded day is simply not complete."""
        h = self.habit()
        st = store.habit_day_state(self.conn, h, D("2026-08-10"))
        self.assertFalse(st["complete"])
        self.assertIsNone(st["state"])
        self.assertTrue(st["scheduled"])

    def test_parent_completes_when_every_subtask_was_ticked(self):
        h = self.habit()
        ids = []
        for i, t in enumerate(["a", "b"]):
            cur = self.conn.execute(
                "INSERT INTO habit_subtasks(habit_id,title,sort_order) VALUES(?,?,?)",
                (h["id"], t, i))
            ids.append(cur.lastrowid)
        self.conn.commit()

        self.complete(h["id"], "2026-08-10", ids[0])
        st = store.habit_day_state(self.conn, h, D("2026-08-10"))
        self.assertFalse(st["complete"])
        self.assertEqual(st["subtasks_done"], 1)

        self.complete(h["id"], "2026-08-10", ids[1])
        st = store.habit_day_state(self.conn, h, D("2026-08-10"))
        self.assertTrue(st["complete"])

    def test_skipped_is_not_completed(self):
        h = self.habit()
        self.complete(h["id"], "2026-08-10", state="skipped")
        st = store.habit_day_state(self.conn, h, D("2026-08-10"))
        self.assertFalse(st["complete"])
        self.assertTrue(st["skipped"])


class Consistency(Base):
    def test_denominator_is_scheduled_days_only(self):
        h = self.habit(schedule="weekdays", config={"days": [0, 2, 4]})
        self.complete(h["id"], "2026-08-10")   # monday
        self.complete(h["id"], "2026-08-12")   # wednesday
        r = store.habit_consistency(self.conn, h["id"], D("2026-08-10"), D("2026-08-16"))
        self.assertEqual(r["scheduled_days"], 3)      # mon, wed, fri
        self.assertEqual(r["completed"], 2)
        self.assertAlmostEqual(r["consistency"], 2 / 3)

    def test_skipped_days_leave_the_denominator(self):
        """an agreed rest day must not be counted as a failure."""
        h = self.habit()
        for d in ["2026-08-10", "2026-08-11", "2026-08-12"]:
            self.complete(h["id"], d)
        self.complete(h["id"], "2026-08-13", state="skipped")
        r = store.habit_consistency(self.conn, h["id"], D("2026-08-10"), D("2026-08-13"))
        self.assertEqual(r["scheduled_days"], 3)
        self.assertEqual(r["skipped"], 1)
        self.assertEqual(r["consistency"], 1.0)

    def test_paused_window_is_not_a_run_of_failures(self):
        h = self.habit(paused_from="2026-08-11", paused_to="2026-08-13")
        self.complete(h["id"], "2026-08-10")
        self.complete(h["id"], "2026-08-14")
        r = store.habit_consistency(self.conn, h["id"], D("2026-08-10"), D("2026-08-14"))
        self.assertEqual(r["scheduled_days"], 2)
        self.assertEqual(r["consistency"], 1.0)
        self.assertEqual([d["status"] for d in r["days"]],
                         ["completed", "paused", "paused", "paused", "completed"])

    def test_no_streak_is_reported(self):
        h = self.habit()
        self.complete(h["id"], "2026-08-10")
        r = store.habit_consistency(self.conn, h["id"], D("2026-08-10"), D("2026-08-12"))
        self.assertNotIn("streak", json.dumps(r).lower())

    def test_min_frequency_is_measured_per_period(self):
        h = self.habit(schedule="min_frequency", config={"times": 2, "period": "week"})
        self.complete(h["id"], "2026-08-10")
        self.complete(h["id"], "2026-08-12")
        self.complete(h["id"], "2026-08-18")
        r = store.habit_consistency(self.conn, h["id"], D("2026-08-10"), D("2026-08-23"))
        self.assertIsNone(r["consistency"])
        self.assertEqual(r["periods_total"], 2)
        self.assertEqual(r["periods_met"], 1)


class MissingValues(Base):
    def test_unknown_days_are_excluded_from_the_average(self):
        self.metric("weight")
        self.observe("weight", "2026-08-10", 80.0)
        self.observe("weight", "2026-08-13", 82.0)
        s = store.metric_series(self.conn, "weight", D("2026-08-10"), D("2026-08-16"))
        self.assertEqual(s["aggregate"]["value"], 81.0)   # not 23.14 from dividing by 7
        self.assertEqual(s["aggregate"]["n"], 2)
        self.assertEqual(s["coverage"]["days_with_data"], 2)
        self.assertEqual(s["coverage"]["days_in_range"], 7)

    def test_zero_semantics_include_missing_days(self):
        self.metric("cigarettes", agg="mean", missing="zero")
        self.observe("cigarettes", "2026-08-10", 4)
        s = store.metric_series(self.conn, "cigarettes", D("2026-08-10"), D("2026-08-13"))
        self.assertEqual(s["aggregate"]["n"], 4)
        self.assertEqual(s["aggregate"]["value"], 1.0)

    def test_the_two_semantics_disagree_on_purpose(self):
        """the same observations must produce different averages under different semantics."""
        self.metric("a", missing="unknown")
        self.metric("b", missing="zero")
        for mid in ("a", "b"):
            self.observe(mid, "2026-08-10", 10)
        ra = store.metric_series(self.conn, "a", D("2026-08-10"), D("2026-08-14"))
        rb = store.metric_series(self.conn, "b", D("2026-08-10"), D("2026-08-14"))
        self.assertEqual(ra["aggregate"]["value"], 10.0)
        self.assertEqual(rb["aggregate"]["value"], 2.0)

    def test_coverage_note_always_states_the_rule(self):
        for sem in ("unknown", "zero", "not_applicable", "incomplete"):
            self.metric("m_" + sem, missing=sem)
            s = store.metric_series(self.conn, "m_" + sem, D("2026-08-10"), D("2026-08-12"))
            self.assertTrue(s["coverage"]["note"], sem)

    def test_estimated_values_are_flagged(self):
        self.metric("sleep")
        self.observe("sleep", "2026-08-10", 7.0)
        self.observe("sleep", "2026-08-11", 7.0, estimated=True,
                     assumption="user said 'about seven'")
        s = store.metric_series(self.conn, "sleep", D("2026-08-10"), D("2026-08-11"))
        self.assertEqual(s["estimated_count"], 1)
        self.assertEqual(s["points"][1]["assumption"], "user said 'about seven'")

    def test_soft_deleted_observations_leave_the_series(self):
        self.metric("weight")
        self.observe("weight", "2026-08-10", 80.0)
        self.observe("weight", "2026-08-11", 999.0)
        self.conn.execute("UPDATE observations SET deleted_at=? WHERE value_num=999.0",
                          (self.now,))
        self.conn.commit()
        s = store.metric_series(self.conn, "weight", D("2026-08-10"), D("2026-08-11"))
        self.assertEqual(s["aggregate"]["value"], 80.0)
        self.assertEqual(len(s["points"]), 1)


class Progress(Base):
    def goal(self, title="g"):
        cur = self.conn.execute(
            "INSERT INTO goals(title,status,created_at,updated_at) VALUES(?,?,?,?)",
            (title, "active", self.now, self.now))
        self.conn.commit()
        return cur.lastrowid

    def test_criteria_are_preferred_over_milestones(self):
        g = self.goal()
        for desc, met in [("a", 1), ("b", 0), ("c", 0), ("d", 0)]:
            self.conn.execute("INSERT INTO success_criteria(goal_id,description,met) "
                              "VALUES(?,?,?)", (g, desc, met))
        self.conn.execute("INSERT INTO milestones(goal_id,title,status) VALUES(?,?,'done')",
                          (g, "m"))
        self.conn.commit()
        p = store.goal_progress(self.conn, g)
        self.assertEqual(p["basis"], "success_criteria")
        self.assertEqual((p["met"], p["total"]), (1, 4))
        self.assertEqual(p["fraction"], 0.25)

    def test_a_goal_with_neither_gets_no_number(self):
        p = store.goal_progress(self.conn, self.goal())
        self.assertEqual(p["basis"], "qualitative")
        self.assertIsNone(p["fraction"])

    def test_project_progress_ignores_elapsed_time(self):
        pid = self.conn.execute(
            "INSERT INTO projects(title,status,deadline,created_at,updated_at) "
            "VALUES('p','active','2026-08-12',?,?)", (self.now, self.now)).lastrowid
        for t, s in [("a", "done"), ("b", "open"), ("c", "open"), ("d", "open")]:
            self.conn.execute("INSERT INTO tasks(project_id,title,status) VALUES(?,?,?)",
                              (pid, t, s))
        self.conn.commit()
        p = store.project_progress(self.conn, pid)
        self.assertEqual(p["basis"], "task_scope")
        self.assertEqual(p["fraction"], 0.25)

    def test_project_with_no_scope_reports_undefined(self):
        pid = self.conn.execute(
            "INSERT INTO projects(title,status,created_at,updated_at) VALUES('p','active',?,?)",
            (self.now, self.now)).lastrowid
        self.conn.commit()
        self.assertIsNone(store.project_progress(self.conn, pid)["fraction"])

    def test_health_is_a_label_with_reasons(self):
        pid = self.conn.execute(
            "INSERT INTO projects(title,status,blocker,created_at,updated_at) "
            "VALUES('p','active','waiting on the electrician',?,?)",
            (self.now, self.now)).lastrowid
        self.conn.commit()
        p = self.conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        h = store.project_health(self.conn, p)
        self.assertEqual(h["health"], "blocked")
        self.assertTrue(h["reasons"])


class Timezone(Base):
    def test_today_is_none_until_a_timezone_is_configured(self):
        """the system refuses to guess a date rather than file a completion on the wrong day."""
        self.assertIsNone(store.today_in_tz(self.conn))
        store.set_setting(self.conn, "timezone", "Europe/Berlin")
        self.assertRegex(store.today_in_tz(self.conn), r"^\d{4}-\d{2}-\d{2}$")

    def test_an_invalid_timezone_does_not_silently_become_utc(self):
        store.set_setting(self.conn, "timezone", "Mars/Olympus_Mons")
        self.assertIsNone(store.today_in_tz(self.conn))


class TodayView(Base):
    def test_unscheduled_habits_stay_off_the_list(self):
        self.habit(title="mwf", schedule="weekdays", config={"days": [0, 2, 4]})
        v = store.today_view(self.conn, D("2026-08-11"))   # tuesday
        self.assertEqual(v["counts"]["total"], 0)

    def test_flexible_habits_appear_until_the_period_target_is_met(self):
        h = self.habit(title="gym", schedule="min_frequency",
                       config={"times": 2, "period": "week"})
        v = store.today_view(self.conn, D("2026-08-11"))
        self.assertEqual(v["counts"]["total"], 1)
        self.assertTrue(v["items"][0]["flexible"])

        self.complete(h["id"], "2026-08-10")
        self.complete(h["id"], "2026-08-11")
        v = store.today_view(self.conn, D("2026-08-12"))
        self.assertEqual([i for i in v["items"] if not i["complete"]], [])

    def test_counts_match_the_items(self):
        h = self.habit(title="daily")
        self.complete(h["id"], "2026-08-11")
        self.habit(title="other")
        v = store.today_view(self.conn, D("2026-08-11"))
        self.assertEqual(v["counts"], {"total": 2, "completed": 1, "remaining": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
