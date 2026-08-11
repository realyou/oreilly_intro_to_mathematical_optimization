---
id: backups
type: index
record_status: current
updated: 2026-08-11
---

# backups

## what makes this backup-friendly

plain markdown, plain directories, no database required to read it. `cp -r` is a valid
backup. so is a git commit. so is a zip on an external disk.

## what to back up

| item | why |
| --- | --- |
| the whole `life-knowledge-base/` directory | the authoritative record |
| `../tracker/life_tracker.db` | dated completions and observations |
| `../../.claude/skills/` | the behavior that reads and writes them |

## what never to back up to a third-party service without explicit approval

all of it. this is personal context. the rule in `agent_rules.md` §7 applies to backups the
same as to exports: no cloud sync, no remote repo, no paste service, no "just to be safe"
upload, without the user saying yes to that specific destination.

## what is never in a backup because it is never written

credentials, keys, seed phrases, recovery codes, payment authentication.
`tracker/.token` is the tracker's local auth token — it is gitignored, and it does not belong
in a backup that leaves the machine.

## restore test

a backup you have not restored is a hypothesis. once, do this:

```bash
cp -r life-knowledge-base /tmp/kb-restore-test
python3 .claude/skills/life-knowledge-base/scripts/kb_validate.py /tmp/kb-restore-test
rm -rf /tmp/kb-restore-test
```

if the validator passes on the copy, the backup is readable standalone.

## derivatives you do not need to back up

indexes, csv exports, charts, the search manifest, and any sqlite cache built from markdown.
all rebuildable. if a restore disagrees with markdown, rebuild the derivative.
