# Running this repo with Claude Code Projects

A project is one coordinating conversation that starts cloud threads (full Claude Code sessions,
each on its own branch) and tracks them. Everything the "chief of staff" playbooks recommend maps
onto a built-in Projects setting. This file is the version for this repository.

Official reference: https://code.claude.com/docs/en/claude-projects

| Playbook ingredient | Where it lives in Projects |
| :- | :- |
| Engagement brief | **Goal** field + **Project settings > Memory > Project instructions** (max 16,000 chars) |
| Workstreams with owners | Threads. One thread per workstream, one draft PR per thread |
| Shared decision file | **Project memory** (`MEMORY.md` index). Say "remember that ..." in any thread |
| Standing rules | Project instructions for the project; `CLAUDE.md` in this repo for repo facts |
| Review gates | "Propose threads and wait for my go-ahead", "Don't open a PR until I've seen the plan" |
| Budget | **Project settings > General**: thread model/effort, coordinator model/effort; **Usage** tab |

## Decide first: is a project the right tool?

Use a project when the work is a stream of related tasks that outlasts one session. For this repo
that is true right now: 18 of 23 scripts fail on current libraries (see the survey below), and the
same fixes recur across sections. Once the code is green again, drop back to single cloud sessions
and a routine. A project with no running threads costs nothing, but every running thread is a full
session against your plan, and a thread that hits the limit resumes by itself when the window resets.

## Setup in seven steps

1. **Prerequisites.** Pro or Max plan with **Projects** in the sidebar at claude.ai/code. Install the
   Claude GitHub App on `realyou/oreilly_intro_to_mathematical_optimization` (a `/web-setup` token
   is not enough for project threads).
2. **Create the project.** Name: "O'Reilly Optimization course". Goal: "Every script in code/ runs
   on current Python libraries and matches the slides."
3. **Add only this repository.** With one repository, threads pick up this repo's `.claude/settings.json`
   permission rules and hooks. Add a second repository and those stop applying in Anthropic-hosted
   environments; you would then rely on auto mode and in-thread approvals.
4. **Paste the project instructions** below into **Project settings > Memory > Project instructions**.
5. **Environment.** In **Project settings > Environment** pick an environment whose network access
   allows `tinyurl.com` and `bit.ly` (several scripts fetch CSVs from there), and whose setup script
   runs `pip install -r requirements.txt`. Or vendor the CSVs into `data/` first and skip the hosts.
6. **Budget.** In **Project settings > General** set Thread model to Sonnet and Thread effort to
   medium for the mechanical fixes. New projects default to Opus at high effort everywhere. Keep
   Coordinator effort low.
7. **First batch.** Send one small thread (the logarithm fix), read how it reports back, then send
   the rest with "propose threads and wait for my go-ahead; run at most two at a time". Remove the
   limits once a few threads come back right.

## Project instructions (paste-ready)

```text
This project maintains the O'Reilly "Intro to Mathematical Optimization" course materials:
code/section_N matches section N of outline.md, code/homework_answers holds solutions,
slides/ and demos/ are binaries that threads never edit.

Workflow
- Branch from master. One draft pull request per thread, titled "section_N: <what changed>".
- Fix the smallest thing that makes a script run on current library versions. Don't restructure,
  add tests, add type hints, or rename files unless the task says so.
- Before you call work done: pip install -r requirements.txt, run every script you touched, and
  paste the last five lines of each run in your final message. Randomised scripts may differ run
  to run; say so rather than "fixing" it.
- Don't change numeric examples that appear on the slides. If a fix would change printed output,
  stop and ask in the thread.

When something is missing
- If a host, package, or file you need is unreachable, say exactly what is missing in your first
  message and stop. Don't mock data, don't swap in a different dataset, don't guess.

What needs my go-ahead
- Merging any pull request. Deleting branches. Changing requirements.txt pins.
- Anything touching slides/, demos/, videos/, or the root .pptx/.pdf.

Coordination
- Propose threads and wait for my go-ahead. Run at most two threads at a time.
- Post only when a thread finishes or is blocked. Answer quick questions here, not in a thread.
- When I correct a thread, remember the correction in project memory.
```

## Engagement 1: make the code run again

Survey on 2026-10-16 with Python 3.13, PuLP 3.3.2, pandas 3.0.5, numpy 2.5.3. Network-blocked
rows failed only because this container couldn't reach `tinyurl.com`/`bit.ly`; they may pass in
an environment that allows those hosts.

| Thread | Scripts | Failure | Fix |
| :- | :- | :- | :- |
| A. PuLP pin | `section_3/knapsack.py`, `section_4/lp1.py`, `lp2.py`, `homework_answers/hw_1.py`, `hw_2.py` | PuLP 4 API | Done: `requirements.txt` pins `pulp>=3,<4`. Thread verifies all five run |
| B. pandas append | `section_2/linear_regression_hc.py`, `quadratic_regression_hc.py`, `quantile_regression_hc.py`, `quadratic_quantile_regression.py` | `DataFrame.append` removed in pandas 2 | Replace with `pd.concat` |
| C. logarithm bug | `section_2/logarithm_hc.py` | `calculate_log` undefined | Call `log(...)` |
| D. remote data | `section_2/k_means_hc.py`, `logistic_regression_hc.py`, both `light_dark_font_*` in sections 2 and 5, `section_5/example_5_3.py`, `homework_answers/hw_3_solution_*.py` | CSV fetch blocked | Confirm they run with hosts allowed; optionally vendor CSVs into `data/` |
| E. homework output | `homework_answers/hw_2.py` | writes `sudokuout.txt` into cwd | Write next to the script or print instead |

Already passing: `section_2/n_root_hc.py`, `square_root_hc.py`, `section_5/example_5_1.py`, `example_5_2.py`.

Threads A, B, C, and E touch disjoint files and can run in parallel. Thread D depends on the
environment change in step 5, so start it last.

## Later engagements for this repo

- **Notebooks.** One thread per section converting its scripts into a teaching notebook with the
  outline's bullets as headings. Gate: you review section 2 before the rest start.
- **Slide check.** A thread that reads `slides/Intro to Optimization.pdf` and lists every number or
  code snippet that no longer matches a script. It reports; you edit the deck.
- **Homework autograder.** Only if you run the course live again. Otherwise skip it.
- **Routine.** Monthly: "pip install -r requirements.txt with no pins relaxed, run every script,
  open an issue listing what broke." Ask for it in the project conversation and it appears on the
  project's **Routines** tab.

## Templates

**Kickoff brief (first message in a new project)**
```text
Goal: <one line>. Repo: <name>, branch from <branch>.
Done means: <observable check>.
Out of scope: <list>.
Propose threads for the work below and wait for my go-ahead. Run at most two at a time.
Work: 1) ... 2) ... 3) ...
```

**Thread task**
```text
Fix <file(s)> so that <observable outcome>. Smallest change that works.
Verify: run <command> and paste the last five lines. Open a draft PR titled "<section>: <change>".
If <thing> is unreachable, say so in your first message and stop.
```

**Decision for memory**
```text
Remember: <decision>, because <reason>. Applies to <scope>. Decided <date>.
```

**Status request**
```text
For every open thread: what it was asked to do, what it assumed or couldn't reach, what it is
waiting on. Don't start anything new.
```

**Memory audit (run monthly or before a big batch)**
```text
List every entry in project memory. For each: still true, outdated, or contradicts another entry.
Propose deletions; don't delete anything yourself.
```

**Closeout**
```text
Engagement <name> is done. For each thread: PR link, merged or not, anything left undone.
Summarise the decisions recorded in memory during this engagement. Mark all idle threads resolved.
```

## Economics on Pro and Max

- Each running thread is a full session. Each thread watching a PR wakes on every CI result and
  review comment. The coordinator spends tokens reading reports.
- Defaults are Opus at high effort for threads. Change this before the first batch (step 6).
- The auto-resume trap: a thread that hits your five-hour or weekly limit retries on its own and
  continues in the next window. If you don't want that, click **Stop** on the thread or **Pause** the
  project in **Project settings > General**.
- A follow-up to a thread idle for over an hour re-reads its whole transcript. For new work, start
  a new thread instead of reviving an old one.
- Check **Project settings > Usage** after the first batch and before scaling up.

## What stays with you

- Merging. Threads open draft PRs and fix CI; you merge.
- Anything on the slides. The deck is the product; scripts serve it, not the other way round.
- Relaxing or changing pins in `requirements.txt`.
- Deleting branches or threads, and any change to `demos/` or `videos/`.

## If you'd rather not use Projects

Everything above except parallel coordination works with plain cloud sessions:

```bash
claude --cloud "Thread B from docs/claude-projects-playbook.md: replace DataFrame.append in the four section_2 regression scripts"
```

`CLAUDE.md`, `requirements.txt`, and `.claude/settings.json` are read by every cloud session, so a
single session gets the same brief, the same verification rule, and the same permissions. Add a
routine for the monthly dependency check. Switch to a project only when you find yourself starting
three or more such sessions at once.
