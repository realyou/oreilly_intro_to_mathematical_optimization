"""end-to-end tests against a real running server: auth boundary, guards, and write flows.

the boundary tests matter most. the promise that "the dashboard is read-only and the agent is
the write interface" is only worth something if the server enforces it — a ui that merely
declines to draw a form is not a control.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tracker"))
import server as srv  # noqa: E402

TOKEN = "test-token-not-a-real-secret"


class ApiCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.httpd, cls.app = srv.serve("127.0.0.1", 0,
                                       str(Path(cls.tmp.name) / "t.db"), TOKEN)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    # -- request helpers --------------------------------------------------------

    def call(self, method, path, body=None, token=TOKEN, opener=None, headers=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            open_fn = opener.open if opener else urllib.request.urlopen
            with open_fn(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def agent(self, method, path, body=None):
        return self.call(method, path, body)

    def web_session(self):
        """sign in the way the browser does, and return an opener carrying the cookie."""
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()))
        status, _ = self.call("POST", "/api/session", {"token": TOKEN},
                              token=None, opener=opener)
        self.assertEqual(status, 200)
        return opener

    def web(self, method, path, body=None, opener=None, csrf=True):
        headers = {"X-Requested-With": "life-tracker"} if csrf else {}
        return self.call(method, path, body, token=None,
                         opener=opener or self.web_session(), headers=headers)


class Auth(ApiCase):
    def test_health_is_open_but_nothing_else_is(self):
        self.assertEqual(self.call("GET", "/api/health", token=None)[0], 200)
        self.assertEqual(self.call("GET", "/api/today", token=None)[0], 401)
        self.assertEqual(self.call("GET", "/api/goals", token=None)[0], 401)

    def test_a_wrong_token_is_rejected(self):
        self.assertEqual(self.call("GET", "/api/goals", token="wrong")[0], 401)
        self.assertEqual(self.call("POST", "/api/session", {"token": "wrong"},
                                   token=None)[0], 401)

    def test_unknown_endpoint_and_wrong_method(self):
        self.assertEqual(self.agent("GET", "/api/nope")[0], 404)
        self.assertEqual(self.agent("DELETE", "/api/goals")[0], 405)

    def test_static_files_cannot_escape_their_directory(self):
        for path in ("/../server.py", "/%2e%2e/server.py", "/static/../../db.py",
                     "/..%2fserver.py"):
            status, _ = self.call("GET", path, token=None)
            self.assertIn(status, (400, 403, 404), path)


class WebBoundary(ApiCase):
    """the browser may tick things off. it may not invent data."""

    def setUp(self):
        self.agent("PATCH", "/api/settings", {"timezone": "Europe/Berlin"})
        _, self.habit = self.agent("POST", "/api/habits",
                                   {"title": "walk", "schedule_type": "daily"})
        self.agent("POST", "/api/metrics", {"id": "mood", "label": "mood", "type": "rating",
                                            "min_value": 1, "max_value": 5})
        self.opener = self.web_session()

    def test_web_may_read_everything(self):
        for path in ("/api/today", "/api/goals", "/api/projects", "/api/metrics",
                     "/api/data/summary", "/api/audit"):
            status, _ = self.web("GET", path, opener=self.opener)
            self.assertEqual(status, 200, path)

    def test_web_may_complete_and_reopen(self):
        hid = self.habit["id"]
        status, _ = self.web("POST", f"/api/habits/{hid}/complete",
                             {"date": "2026-08-10"}, opener=self.opener)
        self.assertEqual(status, 200)
        status, _ = self.web("POST", f"/api/habits/{hid}/reopen",
                             {"date": "2026-08-10"}, opener=self.opener)
        self.assertEqual(status, 200)

    def test_web_may_not_write_observations_goals_projects_or_metrics(self):
        forbidden = [
            ("POST", "/api/observations", {"metric_id": "mood", "value": 5}),
            ("POST", "/api/goals", {"title": "invented"}),
            ("POST", "/api/projects", {"title": "invented"}),
            ("POST", "/api/metrics", {"id": "x", "label": "x", "type": "numeric"}),
            ("PATCH", "/api/settings", {"timezone": "UTC"}),
            ("POST", "/api/events", {"title": "invented"}),
        ]
        for method, path, body in forbidden:
            status, payload = self.web(method, path, body, opener=self.opener)
            self.assertEqual(status, 403, f"{method} {path}")
            self.assertIn("read-only by design", payload["error"])

    def test_web_writes_require_the_csrf_header(self):
        status, payload = self.web("POST", f"/api/habits/{self.habit['id']}/complete",
                                   {"date": "2026-08-10"}, opener=self.opener, csrf=False)
        self.assertEqual(status, 403)
        self.assertIn("X-Requested-With", payload["error"])

    def test_signing_out_invalidates_the_session(self):
        opener = self.web_session()
        self.assertEqual(self.web("GET", "/api/today", opener=opener)[0], 200)
        self.web("DELETE", "/api/session", opener=opener)
        self.assertEqual(self.web("GET", "/api/today", opener=opener)[0], 401)


class Guards(ApiCase):
    def test_today_refuses_to_guess_before_a_timezone_exists(self):
        tmp = tempfile.TemporaryDirectory()
        httpd, _ = srv.serve("127.0.0.1", 0, str(Path(tmp.name) / "fresh.db"), TOKEN)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            base = self.base
            self.base = f"http://127.0.0.1:{httpd.server_address[1]}"
            status, payload = self.agent("GET", "/api/today")
            self.assertEqual(status, 409)
            self.assertIn("timezone", payload["error"])
            # an explicit date still works — the refusal is about guessing, not about dates.
            self.assertEqual(self.agent("GET", "/api/today?date=2026-08-11")[0], 200)
        finally:
            self.base = base
            httpd.shutdown()
            httpd.server_close()
            tmp.cleanup()

    def test_an_invalid_timezone_is_rejected(self):
        status, payload = self.agent("PATCH", "/api/settings",
                                     {"timezone": "Mars/Olympus_Mons"})
        self.assertEqual(status, 400)
        self.assertIn("unknown timezone", payload["error"])

    def test_estimates_must_carry_their_assumption(self):
        self.agent("POST", "/api/metrics", {"id": "sleep", "label": "sleep",
                                            "type": "duration", "unit": "hours"})
        status, payload = self.agent("POST", "/api/observations",
                                     {"metric_id": "sleep", "date": "2026-08-10",
                                      "value": 7, "estimated": True})
        self.assertEqual(status, 400)
        self.assertIn("assumption", payload["error"])

        status, _ = self.agent("POST", "/api/observations",
                               {"metric_id": "sleep", "date": "2026-08-10", "value": 7,
                                "estimated": True, "assumption": "user said 'about seven'"})
        self.assertEqual(status, 200)

    def test_observations_need_a_defined_metric(self):
        status, payload = self.agent("POST", "/api/observations",
                                     {"metric_id": "undefined_thing", "value": 1,
                                      "date": "2026-08-10"})
        self.assertEqual(status, 404)
        self.assertIn("define it first", payload["error"])

    def test_values_outside_the_defined_range_are_rejected(self):
        self.agent("POST", "/api/metrics", {"id": "rating5", "label": "r", "type": "rating",
                                            "min_value": 1, "max_value": 5})
        self.assertEqual(self.agent("POST", "/api/observations",
                                    {"metric_id": "rating5", "value": 9,
                                     "date": "2026-08-10"})[0], 400)

    def test_invalid_missing_semantics_is_rejected(self):
        status, payload = self.agent("POST", "/api/metrics",
                                     {"id": "bad", "label": "bad", "type": "numeric",
                                      "missing_semantics": "whatever"})
        self.assertEqual(status, 400)
        self.assertIn("four different", payload["error"])

    def test_pausing_a_goal_requires_a_reason(self):
        _, goal = self.agent("POST", "/api/goals", {"title": "a goal"})
        status, payload = self.agent("PATCH", f"/api/goals/{goal['id']}",
                                     {"status": "paused"})
        self.assertEqual(status, 400)
        self.assertIn("status_reason", payload["error"])
        self.assertEqual(self.agent("PATCH", f"/api/goals/{goal['id']}",
                                    {"status": "paused",
                                     "status_reason": "injury"})[0], 200)

    def test_deleting_an_unknown_observation_says_read_first(self):
        status, payload = self.agent("DELETE", "/api/observations/999999")
        self.assertEqual(status, 404)
        self.assertIn("never guess", payload["error"])

    def test_completing_a_subtask_of_another_habit_is_rejected(self):
        _, a = self.agent("POST", "/api/habits", {"title": "a", "schedule_type": "daily",
                                                  "subtasks": ["one"]})
        _, b = self.agent("POST", "/api/habits", {"title": "b", "schedule_type": "daily"})
        sub = a["subtasks"][0]["id"]
        self.assertEqual(self.agent("POST", f"/api/habits/{b['id']}/complete",
                                    {"date": "2026-08-10", "subtask_id": sub})[0], 404)

    def test_reopening_something_never_completed_is_a_404(self):
        _, h = self.agent("POST", "/api/habits", {"title": "h", "schedule_type": "daily"})
        self.assertEqual(self.agent("POST", f"/api/habits/{h['id']}/reopen",
                                    {"date": "2026-08-10"})[0], 404)

    def test_weekdays_schedule_needs_its_days(self):
        self.assertEqual(self.agent("POST", "/api/habits",
                                    {"title": "x", "schedule_type": "weekdays"})[0], 400)


class WriteFlows(ApiCase):
    def setUp(self):
        self.agent("PATCH", "/api/settings", {"timezone": "Europe/Berlin"})

    def test_a_correction_preserves_the_previous_value(self):
        self.agent("POST", "/api/metrics", {"id": "w2", "label": "w", "type": "numeric"})
        _, obs = self.agent("POST", "/api/observations",
                            {"metric_id": "w2", "date": "2026-08-10", "value": 80})
        self.agent("PATCH", f"/api/observations/{obs['id']}", {"value": 82})

        _, back = self.agent("GET", "/api/observations?metric_id=w2")
        self.assertEqual(back["observations"][0]["value_num"], 82.0)

        _, audit = self.agent("GET", "/api/audit?limit=10")
        correction = next(a for a in audit["audit"] if a["action"] == "correct")
        self.assertIn("80", correction["detail"])

    def test_deletion_is_soft_and_the_value_survives_in_the_audit_log(self):
        self.agent("POST", "/api/metrics", {"id": "w3", "label": "w", "type": "numeric"})
        _, obs = self.agent("POST", "/api/observations",
                            {"metric_id": "w3", "date": "2026-08-10", "value": 77})
        self.agent("DELETE", f"/api/observations/{obs['id']}")

        _, back = self.agent("GET", "/api/observations?metric_id=w3")
        self.assertEqual(back["observations"], [])

        _, audit = self.agent("GET", "/api/audit?limit=10")
        deletion = next(a for a in audit["audit"] if a["action"] == "delete")
        self.assertIn("77", deletion["detail"])

    def test_reopening_records_the_state_it_removed(self):
        _, h = self.agent("POST", "/api/habits", {"title": "r", "schedule_type": "daily"})
        self.agent("POST", f"/api/habits/{h['id']}/complete", {"date": "2026-08-10"})
        self.agent("POST", f"/api/habits/{h['id']}/reopen", {"date": "2026-08-10"})
        _, audit = self.agent("GET", "/api/audit?limit=5")
        entry = next(a for a in audit["audit"] if a["action"] == "habit_reopen")
        self.assertIn("completed", entry["detail"])

    def test_observation_response_reports_the_updated_aggregate(self):
        self.agent("POST", "/api/metrics", {"id": "agg", "label": "agg", "type": "numeric"})
        self.agent("POST", "/api/observations",
                   {"metric_id": "agg", "date": "2026-08-09", "value": 10})
        _, obs = self.agent("POST", "/api/observations",
                            {"metric_id": "agg", "date": "2026-08-10", "value": 20})
        self.assertEqual(obs["aggregate_30d"]["value"], 15.0)
        self.assertEqual(obs["aggregate_30d"]["n"], 2)

    def test_the_full_goal_hierarchy_links_up(self):
        _, goal = self.agent("POST", "/api/goals", {
            "title": "ship the thing", "life_area": "craft", "outcome": "it is shipped",
            "criteria": [{"description": "users can sign up"}],
            "milestones": [{"title": "alpha"}]})
        _, project = self.agent("POST", "/api/projects", {
            "title": "build it", "goal_id": goal["id"], "tasks": ["scaffold", "deploy"]})
        _, habit = self.agent("POST", "/api/habits", {
            "title": "daily push", "schedule_type": "daily", "goal_id": goal["id"]})

        _, full = self.agent("GET", f"/api/goals/{goal['id']}")
        self.assertEqual(full["area"], "craft")
        self.assertEqual(full["progress"]["basis"], "success_criteria")
        self.assertEqual(full["next_milestone"]["title"], "alpha")
        self.assertEqual([p["id"] for p in full["projects"]], [project["id"]])
        self.assertEqual([h["id"] for h in full["habits"]], [habit["id"]])

        _, today = self.agent("GET", "/api/today?date=2026-08-11")
        pushes = [i for i in today["items"] if i["title"] == "daily push"]
        self.assertEqual(pushes[0]["supports"], "ship the thing")

    def test_meeting_a_criterion_moves_progress(self):
        _, goal = self.agent("POST", "/api/goals", {
            "title": "g", "criteria": [{"description": "a"}, {"description": "b"}]})
        cid = goal["criteria"][0]["id"]
        _, after = self.agent("PATCH", f"/api/criteria/{cid}", {"met": True})
        self.assertEqual(after["progress"]["met"], 1)
        self.assertEqual(after["progress"]["fraction"], 0.5)

    def test_task_completion_appears_and_then_collapses_by_date(self):
        _, p = self.agent("POST", "/api/projects", {"title": "proj", "tasks": ["one"]})
        tid = p["tasks"][0]["id"]
        self.agent("POST", f"/api/tasks/{tid}/complete", {"date": "2026-08-10"})

        _, day = self.agent("GET", "/api/today?date=2026-08-10")
        self.assertEqual(day["counts"]["completed"], 1)
        # a task completed yesterday does not clutter today
        _, next_day = self.agent("GET", "/api/today?date=2026-08-11")
        self.assertNotIn("one", [i["title"] for i in next_day["items"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
