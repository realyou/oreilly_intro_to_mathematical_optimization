#!/usr/bin/env python3
"""command-line client for the life tracker api. stdlib only.

    python3 tracker.py today
    python3 tracker.py complete --habit 3 --date 2026-08-11
    python3 tracker.py log --metric sleep_hours --value 7.5 --date 2026-08-11
    python3 tracker.py trend --habit 3 --days 30

the token comes from $LIFE_TRACKER_TOKEN or `life-os/tracker/.token`; the base url from
$LIFE_TRACKER_URL (default http://127.0.0.1:8787). the token is never printed, never echoed
into output, and never passed on the command line.

every subcommand prints the server's json. read it back before reporting anything to the
user — that is the point of having a client rather than guessing what a write did.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = os.environ.get("LIFE_TRACKER_URL", "http://127.0.0.1:8787")
TOKEN_FILE = Path(__file__).resolve().parents[3] / "life-os" / "tracker" / ".token"


def token() -> str:
    t = os.environ.get("LIFE_TRACKER_TOKEN")
    if t:
        return t.strip()
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    sys.exit("no token: set LIFE_TRACKER_TOKEN or start the server once to create "
             f"{TOKEN_FILE}")


def call(method: str, path: str, body=None, query=None):
    url = DEFAULT_URL.rstrip("/") + path
    if query:
        from urllib.parse import urlencode

        clean = {k: v for k, v in query.items() if v is not None}
        if clean:
            url += "?" + urlencode(clean)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token()}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        payload = e.read().decode(errors="replace")
        try:
            msg = json.loads(payload).get("error", payload)
        except json.JSONDecodeError:
            msg = payload
        sys.exit(f"error {e.code}: {msg}")
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach the tracker at {DEFAULT_URL}: {e.reason}\n"
                 "start it with: python3 life-os/tracker/server.py")


def show(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def kv(pairs):
    """--set key=value pairs into a dict, with json values where they parse."""
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser(description="life tracker client")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, help_):
        return sub.add_parser(name, help=help_)

    p = add("today", "read a day's checklist")
    p.add_argument("--date")

    p = add("complete", "record a completion — only from an explicit user action")
    p.add_argument("--habit", type=int)
    p.add_argument("--task", type=int)
    p.add_argument("--subtask", type=int)
    p.add_argument("--date")
    p.add_argument("--state", choices=["completed", "skipped"], default="completed")
    p.add_argument("--note")

    p = add("reopen", "undo a completion")
    p.add_argument("--habit", type=int)
    p.add_argument("--task", type=int)
    p.add_argument("--subtask", type=int)
    p.add_argument("--date")

    add("habits", "list habits")
    p = add("habit-add", "create a habit")
    p.add_argument("--title", required=True)
    p.add_argument("--schedule", required=True,
                   choices=["daily", "weekdays", "interval", "min_frequency", "weekly"])
    p.add_argument("--config", default="{}",
                   help='json: {"days":[0,2,4]} | {"every_n_days":3} | {"times":3,"period":"week"}')
    p.add_argument("--goal", type=int)
    p.add_argument("--project", type=int)
    p.add_argument("--subtasks", nargs="*", default=[])
    p.add_argument("--safety-note")

    p = add("habit-set", "update a habit (pause, retitle, relink, reschedule)")
    p.add_argument("id", type=int)
    p.add_argument("--set", nargs="+", required=True, metavar="key=value")

    p = add("trend", "habit consistency over scheduled days")
    p.add_argument("--habit", type=int, required=True)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--end")

    add("goals", "list goals with progress")
    p = add("goal", "read one goal")
    p.add_argument("id", type=int)
    p = add("goal-add", "create a goal")
    p.add_argument("--title", required=True)
    p.add_argument("--area")
    p.add_argument("--outcome")
    p.add_argument("--dod", help="definition of done")
    p.add_argument("--rationale")
    p.add_argument("--baseline")
    p.add_argument("--target-date")
    p.add_argument("--review")
    p.add_argument("--kb-path")
    p.add_argument("--criteria", nargs="*", default=[])
    p.add_argument("--milestones", nargs="*", default=[])
    p = add("goal-set", "update a goal")
    p.add_argument("id", type=int)
    p.add_argument("--set", nargs="+", required=True, metavar="key=value")
    p = add("criterion", "add or mark a success criterion")
    p.add_argument("--goal", type=int)
    p.add_argument("--add")
    p.add_argument("--id", type=int)
    p.add_argument("--met", action="store_true")
    p.add_argument("--unmet", action="store_true")

    p = add("milestone", "add or update a milestone")
    p.add_argument("--goal", type=int)
    p.add_argument("--project", type=int)
    p.add_argument("--add")
    p.add_argument("--id", type=int)
    p.add_argument("--status", choices=["open", "done"])
    p.add_argument("--target-date")

    add("projects", "list projects with health and next action")
    p = add("project-add", "create a project")
    p.add_argument("--title", required=True)
    p.add_argument("--purpose")
    p.add_argument("--goal", type=int)
    p.add_argument("--phase")
    p.add_argument("--owner")
    p.add_argument("--deadline")
    p.add_argument("--kb-path")
    p.add_argument("--tasks", nargs="*", default=[])
    p = add("project-set", "update a project")
    p.add_argument("id", type=int)
    p.add_argument("--set", nargs="+", required=True, metavar="key=value")

    p = add("task-add", "add a task")
    p.add_argument("--title", required=True)
    p.add_argument("--project", type=int)
    p.add_argument("--goal", type=int)
    p.add_argument("--milestone", type=int)
    p.add_argument("--parent", type=int)
    p.add_argument("--due")

    add("metrics", "list metric definitions")
    p = add("metric-add", "define a metric")
    p.add_argument("--id", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--type", required=True,
                   choices=["numeric", "boolean", "categorical", "duration", "count",
                            "rating", "text"])
    p.add_argument("--unit")
    p.add_argument("--min", type=float)
    p.add_argument("--max", type=float)
    p.add_argument("--options", nargs="*")
    p.add_argument("--aggregation", default="mean",
                   choices=["mean", "sum", "last", "count", "distribution", "none"])
    p.add_argument("--chart", default="line",
                   choices=["line", "bar", "calendar", "count", "distribution",
                            "categorical_history"])
    p.add_argument("--missing", default="unknown",
                   choices=["unknown", "zero", "not_applicable", "incomplete"],
                   help="what a day with no observation means. this changes every average.")
    p = add("metric-set", "update a metric definition")
    p.add_argument("id")
    p.add_argument("--set", nargs="+", required=True, metavar="key=value")

    p = add("log", "record an observation")
    p.add_argument("--metric", required=True)
    p.add_argument("--value", required=True)
    p.add_argument("--date")
    p.add_argument("--unit")
    p.add_argument("--note")
    p.add_argument("--source")
    p.add_argument("--estimated", action="store_true",
                   help="agent-derived value; requires --assumption")
    p.add_argument("--assumption")

    p = add("series", "read a metric series with coverage")
    p.add_argument("--metric", required=True)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--end")

    p = add("obs", "list observations (read before correcting or deleting)")
    p.add_argument("--metric")
    p.add_argument("--date")
    p.add_argument("--limit", type=int, default=20)
    p = add("obs-correct", "correct an observation by id")
    p.add_argument("id", type=int)
    p.add_argument("--set", nargs="+", required=True, metavar="key=value")
    p = add("obs-delete", "soft-delete an observation by id")
    p.add_argument("id", type=int)

    p = add("event", "record a dated life event")
    p.add_argument("--title", required=True)
    p.add_argument("--date")
    p.add_argument("--category")
    p.add_argument("--detail")
    p.add_argument("--kb-path")

    p = add("link", "link two entities")
    p.add_argument("--from-type", required=True)
    p.add_argument("--from-id", required=True)
    p.add_argument("--to-type", required=True)
    p.add_argument("--to-id", required=True)
    p.add_argument("--relation", default="supports")

    p = add("data", "dashboard summary")
    p.add_argument("--days", type=int, default=30)

    add("settings", "read settings")
    p = add("settings-set", "set timezone, name, or kb path")
    p.add_argument("--set", nargs="+", required=True, metavar="key=value")

    p = add("audit", "recent writes")
    p.add_argument("--limit", type=int, default=20)

    a = ap.parse_args()
    c = a.cmd

    if c == "today":
        return show(call("GET", "/api/today", query={"date": a.date}))

    if c in ("complete", "reopen"):
        if not (a.habit or a.task):
            sys.exit("pass --habit or --task")
        body = {"date": a.date}
        if a.habit:
            if a.subtask:
                body["subtask_id"] = a.subtask
            if c == "complete":
                body["state"] = a.state
                if a.note:
                    body["note"] = a.note
            return show(call("POST", f"/api/habits/{a.habit}/{c}", body))
        return show(call("POST", f"/api/tasks/{a.task}/"
                                 f"{'complete' if c == 'complete' else 'reopen'}", body))

    if c == "habits":
        return show(call("GET", "/api/habits"))
    if c == "habit-add":
        return show(call("POST", "/api/habits", {
            "title": a.title, "schedule_type": a.schedule,
            "schedule_config": json.loads(a.config), "goal_id": a.goal,
            "project_id": a.project, "subtasks": a.subtasks,
            "safety_note": a.safety_note}))
    if c == "habit-set":
        return show(call("PATCH", f"/api/habits/{a.id}", kv(a.set)))
    if c == "trend":
        return show(call("GET", f"/api/habits/{a.habit}/trend",
                         query={"days": a.days, "end": a.end}))

    if c == "goals":
        return show(call("GET", "/api/goals"))
    if c == "goal":
        return show(call("GET", f"/api/goals/{a.id}"))
    if c == "goal-add":
        return show(call("POST", "/api/goals", {
            "title": a.title, "life_area": a.area, "outcome": a.outcome,
            "definition_of_done": a.dod, "rationale": a.rationale, "baseline": a.baseline,
            "target_date": a.target_date, "next_review": a.review, "kb_path": a.kb_path,
            "status": "active",
            "criteria": [{"description": d} for d in a.criteria],
            "milestones": [{"title": t} for t in a.milestones]}))
    if c == "goal-set":
        return show(call("PATCH", f"/api/goals/{a.id}", kv(a.set)))
    if c == "criterion":
        if a.add:
            if not a.goal:
                sys.exit("--add needs --goal")
            return show(call("POST", f"/api/goals/{a.goal}/criteria", {"description": a.add}))
        if not a.id:
            sys.exit("pass --add or --id")
        return show(call("PATCH", f"/api/criteria/{a.id}", {"met": a.met and not a.unmet}))
    if c == "milestone":
        if a.add:
            return show(call("POST", "/api/milestones", {
                "goal_id": a.goal, "project_id": a.project, "title": a.add,
                "target_date": a.target_date}))
        if not a.id:
            sys.exit("pass --add or --id")
        return show(call("PATCH", f"/api/milestones/{a.id}",
                         {"status": a.status, "target_date": a.target_date}))

    if c == "projects":
        return show(call("GET", "/api/projects"))
    if c == "project-add":
        return show(call("POST", "/api/projects", {
            "title": a.title, "purpose": a.purpose, "goal_id": a.goal, "phase": a.phase,
            "owner": a.owner, "deadline": a.deadline, "kb_path": a.kb_path,
            "tasks": [{"title": t} for t in a.tasks]}))
    if c == "project-set":
        return show(call("PATCH", f"/api/projects/{a.id}", kv(a.set)))
    if c == "task-add":
        return show(call("POST", "/api/tasks", {
            "title": a.title, "project_id": a.project, "goal_id": a.goal,
            "milestone_id": a.milestone, "parent_id": a.parent, "due_date": a.due}))

    if c == "metrics":
        return show(call("GET", "/api/metrics"))
    if c == "metric-add":
        return show(call("POST", "/api/metrics", {
            "id": a.id, "label": a.label, "type": a.type, "unit": a.unit,
            "min_value": a.min, "max_value": a.max, "options": a.options,
            "aggregation": a.aggregation, "chart": a.chart, "missing_semantics": a.missing}))
    if c == "metric-set":
        return show(call("PATCH", f"/api/metrics/{a.id}", kv(a.set)))

    if c == "log":
        try:
            value = json.loads(a.value)
        except json.JSONDecodeError:
            value = a.value
        return show(call("POST", "/api/observations", {
            "metric_id": a.metric, "value": value, "date": a.date, "unit": a.unit,
            "note": a.note, "source": a.source, "estimated": a.estimated,
            "assumption": a.assumption}))
    if c == "series":
        return show(call("GET", f"/api/metrics/{a.metric}/series",
                         query={"days": a.days, "end": a.end}))
    if c == "obs":
        return show(call("GET", "/api/observations",
                         query={"metric_id": a.metric, "date": a.date, "limit": a.limit}))
    if c == "obs-correct":
        return show(call("PATCH", f"/api/observations/{a.id}", kv(a.set)))
    if c == "obs-delete":
        return show(call("DELETE", f"/api/observations/{a.id}"))

    if c == "event":
        return show(call("POST", "/api/events", {
            "title": a.title, "date": a.date, "category": a.category, "detail": a.detail,
            "kb_path": a.kb_path}))
    if c == "link":
        return show(call("POST", "/api/links", {
            "from_type": a.from_type, "from_id": a.from_id, "to_type": a.to_type,
            "to_id": a.to_id, "relation": a.relation}))

    if c == "data":
        return show(call("GET", "/api/data/summary", query={"days": a.days}))
    if c == "settings":
        return show(call("GET", "/api/settings"))
    if c == "settings-set":
        return show(call("PATCH", "/api/settings", kv(a.set)))
    if c == "audit":
        return show(call("GET", "/api/audit", query={"limit": a.limit}))


if __name__ == "__main__":
    main()
