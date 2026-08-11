"""tests for the knowledge-base scripts.

two things are checked: the real knowledge base is clean, and the validator actually catches
the failures it claims to catch. a validator that passes everything is worse than none — it
manufactures confidence.
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "life-os" / "life-knowledge-base"
SCRIPTS = ROOT / ".claude" / "skills" / "life-knowledge-base" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import kb_validate  # noqa: E402
import kb_search  # noqa: E402
import kbio  # noqa: E402


def run_validator(root: Path):
    rep = kb_validate.Report()
    kb_validate.validate(root, rep)
    return rep


def messages(rep):
    return " | ".join(m for _p, _l, m in rep.errors)


class RealKnowledgeBase(unittest.TestCase):
    def test_the_shipped_knowledge_base_validates(self):
        rep = run_validator(KB)
        self.assertEqual(rep.errors, [], messages(rep))

    def test_every_documented_directory_exists(self):
        for d in ["00-index", "01-inbox", "10-profile", "20-timeline/events",
                  "30-health/conditions", "30-health/medications", "30-health/procedures",
                  "30-health/tests", "30-health/logs", "40-nutrition/logs",
                  "50-projects/projects", "60-finance", "70-goals/goals", "75-ideas/ideas",
                  "80-interests", "85-resources", "90-sources/records", "90-sources/files",
                  "95-system/templates"]:
            self.assertTrue((KB / d).is_dir(), d)

    def test_the_entry_points_exist(self):
        for f in ["readme.md", "agent_rules.md", "00-index/master_index.md",
                  "00-index/open_questions.md", "00-index/people_index.md",
                  "00-index/projects_index.md", "00-index/sources_index.md",
                  "01-inbox/inbox.md", "10-profile/profile.md", "20-timeline/timeline.md",
                  "30-health/health_summary.md", "40-nutrition/nutrition_summary.md",
                  "50-projects/projects_summary.md", "60-finance/finance_summary.md",
                  "70-goals/goals_summary.md", "75-ideas/ideas_index.md",
                  "80-interests/interests_summary.md", "85-resources/resources.md",
                  "95-system/schema.md", "95-system/changelog.md", "95-system/intake.md",
                  "95-system/backups.md"]:
            self.assertTrue((KB / f).is_file(), f)

    def test_the_master_index_links_every_canonical_summary(self):
        text = (KB / "00-index" / "master_index.md").read_text()
        for summary in ["profile", "timeline", "health_summary", "nutrition_summary",
                        "projects_summary", "finance_summary", "goals_summary",
                        "ideas_index", "interests_summary", "resources"]:
            self.assertIn(summary, text)

    def test_no_personal_facts_were_invented_during_setup(self):
        """the onboarding answers must still be unanswered — nothing was guessed."""
        profile = (KB / "10-profile" / "profile.md").read_text()
        self.assertEqual(profile.count("_unanswered_"), 4)
        self.assertIn("_unknown_", profile)

    def test_a_template_is_available_for_each_core_record_type(self):
        for t in ["event", "source", "project", "goal", "person", "decision", "idea",
                  "condition", "medication", "resource"]:
            self.assertTrue((KB / "95-system" / "templates" / f"{t}.md").is_file(), t)


class ValidatorCatchesProblems(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "95-system").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def good(self, ident="evt-20260810-001", **over):
        fm = {"id": ident, "type": "event", "record_status": "current",
              "epistemic": "self_report", "occurred_at": "2026-08-10",
              "recorded_at": "2026-08-10"}
        fm.update(over)
        body = "\n".join(f"{k}: {v}" for k, v in fm.items())
        return f"---\n{body}\n---\n\n# a title\n\nsome text.\n"

    def test_a_clean_record_produces_no_errors(self):
        self.write("a.md", self.good())
        self.assertEqual(run_validator(self.root).errors, [])

    def test_duplicate_ids(self):
        self.write("a.md", self.good())
        self.write("b.md", self.good())
        self.assertIn("duplicate id", messages(run_validator(self.root)))

    def test_a_non_iso_date(self):
        self.write("a.md", self.good(occurred_at="10/08/2026"))
        self.assertIn("not an ISO date", messages(run_validator(self.root)))

    def test_recorded_before_it_happened(self):
        self.write("a.md", self.good(occurred_at="2026-08-10", recorded_at="2026-08-01"))
        self.assertIn("after recorded_at", messages(run_validator(self.root)))

    def test_validity_window_backwards(self):
        self.write("a.md", self.good(valid_from="2026-08-10", valid_to="2026-08-01"))
        self.assertIn("valid_from", messages(run_validator(self.root)))

    def test_an_invalid_enum_value(self):
        self.write("a.md", self.good(record_status="probably_true"))
        self.assertIn("record_status", messages(run_validator(self.root)))
        self.write("b.md", self.good(ident="evt-20260810-002", epistemic="vibes"))
        self.assertIn("epistemic", messages(run_validator(self.root)))

    def test_a_dangling_supersedes_reference(self):
        self.write("a.md", self.good(supersedes="[evt-19990101-001]"))
        self.assertIn("no record defines", messages(run_validator(self.root)))

    def test_a_resolved_supersedes_reference_is_fine(self):
        self.write("old.md", self.good(ident="evt-20260101-001"))
        self.write("new.md", self.good(ident="evt-20260810-002",
                                       supersedes="[evt-20260101-001]"))
        self.assertEqual(run_validator(self.root).errors, [])

    def test_a_broken_internal_link(self):
        self.write("a.md", self.good() + "\nsee [the note](./nowhere.md).\n")
        self.assertIn("link target does not exist", messages(run_validator(self.root)))

    def test_a_working_internal_link_and_external_urls_are_left_alone(self):
        self.write("target.md", self.good(ident="evt-20260810-009"))
        self.write("a.md", self.good() +
                   "\nsee [it](./target.md) and [the web](https://example.org).\n")
        self.assertEqual(run_validator(self.root).errors, [])

    def test_unclosed_frontmatter(self):
        self.write("a.md", "---\nid: evt-20260810-001\ntype: event\n\n# no close\n")
        self.assertIn("never closed", messages(run_validator(self.root)))

    def test_a_ragged_csv_export(self):
        self.write("a.md", self.good())          # a knowledge base always has markdown
        self.write("95-system/export.csv", "date,metric,value\n2026-08-10,weight\n")
        self.assertIn("header has 3", messages(run_validator(self.root)))

    def test_a_directory_with_no_markdown_is_reported_as_not_a_knowledge_base(self):
        self.write("95-system/export.csv", "date,value\n2026-08-10,1\n")
        self.assertIn("no markdown files", messages(run_validator(self.root)))

    def test_templates_are_not_validated_as_records(self):
        """templates carry placeholders on purpose; flagging them would train you to ignore
        the validator, which is how a real error gets missed."""
        self.write("95-system/templates/event.md",
                   "---\nid: evt-YYYYMMDD-NNN\ntype: event\nrecord_status: current | historical\n"
                   "occurred_at: YYYY-MM-DD\n---\n\n# template\n")
        self.assertEqual(run_validator(self.root).errors, [])


class SecretsAreNeverStoredOrPrinted(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, content):
        (self.root / "note.md").write_text(content)
        return run_validator(self.root)

    def test_common_secret_shapes_are_caught(self):
        for secret in [
            "api_key: sk-abcdefghijklmnopqrstuvwx",
            "password: hunter2correcthorse",
            "token = ghp_abcdefghijklmnopqrstuvwxyz012345",
            "aws: AKIAIOSFODNN7EXAMPLE",
            "-----BEGIN RSA PRIVATE KEY-----",
        ]:
            rep = self.check(f"# note\n\n{secret}\n")
            self.assertTrue(rep.errors, f"not caught: {secret.split(':')[0]}")

    def test_the_secret_value_is_never_printed(self):
        """the finding must be actionable without copying the secret into a transcript."""
        rep = self.check("# note\n\napi_key: sk-supersecretvalue12345678\n")
        printed = " ".join(f"{p} {line} {msg}" for p, line, msg in rep.errors)
        self.assertNotIn("supersecretvalue", printed)
        self.assertIn("possible", printed)

    def test_talking_about_secrets_is_not_a_finding(self):
        for line in [
            "never store passwords, keys, or seed phrases here",
            "| never store | credentials, passwords, api keys |",
            "do not record the password anywhere",
        ]:
            self.assertEqual(self.check(f"# note\n\n{line}\n").errors, [], line)

    def test_the_real_knowledge_base_holds_no_secrets(self):
        rep = run_validator(KB)
        self.assertEqual([m for _p, _l, m in rep.errors if "possible" in m], [])


class Search(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        (self.root / name).write_text(text)

    def score(self, name, terms, include_all=False):
        return kb_search.score_file(self.root / name, self.root, terms, include_all)

    def test_a_match_in_the_id_outranks_a_match_in_the_body(self):
        self.write("id.md", "---\nid: cond-migraine\ntype: condition\n---\n\n# a thing\n")
        self.write("body.md", "---\nid: evt-20260810-001\n---\n\n# note\n\nmigraine, once.\n")
        self.assertGreater(self.score("id.md", ["migraine"])["score"],
                           self.score("body.md", ["migraine"])["score"])

    def test_superseded_records_are_pushed_down_but_still_findable(self):
        base = "---\nid: {}\nrecord_status: {}\n---\n\n# dose\n\nlevothyroxine 50 mcg\n"
        self.write("cur.md", base.format("med-levo", "current"))
        self.write("old.md", base.format("med-levo-old", "superseded"))
        cur = self.score("cur.md", ["levothyroxine"])
        old = self.score("old.md", ["levothyroxine"])
        self.assertGreater(cur["score"], old["score"])
        self.assertIsNotNone(old)          # still findable — history is not hidden
        self.assertEqual(old["status"], "superseded")

    def test_every_term_must_appear(self):
        self.write("a.md", "# note\n\nonly apples here\n")
        self.assertIsNone(self.score("a.md", ["apples", "oranges"]))
        self.assertIsNotNone(self.score("a.md", ["apples"]))

    def test_searching_the_real_knowledge_base_finds_the_rules(self):
        out = io.StringIO()
        argv = sys.argv
        sys.argv = ["kb_search.py", "privacy", "--root", str(KB), "--limit", "5"]
        try:
            with redirect_stdout(out):
                kb_search.main()
        finally:
            sys.argv = argv
        self.assertIn("agent_rules.md", out.getvalue())


class Frontmatter(unittest.TestCase):
    def test_inline_and_block_lists_both_parse(self):
        fm = kbio.parse_yaml_ish(
            "id: evt-1\ntags: [health, sleep]\nsource_ids:\n  - src-1\n  - src-2\n"
            "valid_to: null\nneeds_verification: false\n")
        self.assertEqual(fm["tags"], ["health", "sleep"])
        self.assertEqual(fm["source_ids"], ["src-1", "src-2"])
        self.assertIsNone(fm["valid_to"])
        self.assertIs(fm["needs_verification"], False)

    def test_a_file_without_frontmatter_is_not_an_error(self):
        fm, body, ok = kbio.split_frontmatter("# just a heading\n\ntext\n")
        self.assertTrue(ok)
        self.assertEqual(fm, {})
        self.assertIn("just a heading", body)


class CommandLine(unittest.TestCase):
    """the scripts must work as documented, from a shell, on the real knowledge base."""

    def run_script(self, *args):
        return subprocess.run([sys.executable, *args], capture_output=True, text=True,
                              cwd=str(ROOT), timeout=60)

    def test_validator_exits_zero_on_the_real_knowledge_base(self):
        r = self.run_script(str(SCRIPTS / "kb_validate.py"), str(KB))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 errors", r.stdout)

    def test_validator_exits_nonzero_when_it_finds_something(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.md").write_text(
                "---\nid: evt-1\noccurred_at: not-a-date\n---\n\n# bad\n")
            r = self.run_script(str(SCRIPTS / "kb_validate.py"), tmp)
            self.assertEqual(r.returncode, 1)

    def test_index_reports_and_writes_only_when_asked(self):
        r = self.run_script(str(SCRIPTS / "kb_index.py"), str(KB))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("records:", r.stdout)
        self.assertFalse((KB / "95-system" / "search_manifest.json").exists(),
                         "kb_index.py wrote a manifest without --write")


if __name__ == "__main__":
    unittest.main(verbosity=2)
