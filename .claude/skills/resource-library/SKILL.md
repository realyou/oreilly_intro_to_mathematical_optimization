---
name: resource-library
description: >
  save, organize, and retrieve external resources — urls, tools, docs, articles, repos,
  courses. use when the user shares a link or asks you to save, bookmark, or remember a
  resource; when they ask "what was that tool", "did i save something about x", or ask for a
  recommendation that a previously saved resource might answer. always search the library
  before recommending anything new.
version: 1.0.0
tags: [resources, urls, tools, bookmarks, provenance]
---

# resource-library

the library exists so a saved link is still useful a year later. that requires reading the
source before summarizing it, and recording *why* it was saved.

## the hard rule

**read the original source before writing a single word about it.**

a summary written from a url, a title, or what you already believe about the project is a
fabrication that will look exactly like knowledge later. if you cannot open the source:

> saved the url with the date. i could not open it, so there is no summary — the entry says
> so, and it will need a read before it is relied on.

that is the correct outcome, and it is honest. an unsummarized entry is not a failure; a
confidently wrong summary is.

## saving a resource

1. **open the url.**
2. store the **canonical** url — the real destination, not a shortener, tracker, or
   redirect — and the **date accessed**.
3. record:
   - **purpose** — what it is for
   - **useful for** — specific capabilities or ideas, from what you actually read
   - **limits** — what it does not do; cost, platform, licence
   - **retrieval trigger** — the future situation in which this should resurface. this field
     is what makes the library work; without it you have a pile of links.
4. **commands only if the source documents them.** never reconstruct an install command from
   memory — versions and flags drift, and a wrong command wastes an hour or breaks something.
5. **status**: `unverified` (saved, not tried) · `tried` · `in use` · `rejected` (with reason).
   saving is bookmarking, not vouching.

entries live in `85-resources/resources.md`, categorized. when the file gets big enough to
hurt retrieval, split it by category and keep the index. a resource that deserves its own note
gets a `res-` id.

## entry shape

```markdown
### res-slug — name
- url: <canonical url>
- accessed: YYYY-MM-DD
- purpose: …
- useful for: …
- limits: …
- retrieval trigger: …
- commands: only if documented at the source
- status: unverified | tried | in use | rejected (reason)
```

## before recommending anything

```bash
python3 .claude/skills/life-knowledge-base/scripts/kb_search.py "<topic>" --limit 10
```

search the library first. recommending a shiny new tool when the user already saved and
rejected it six months ago — for a reason they wrote down — is worse than useless.

if a saved resource matches, say when it was saved, what its status is, and that entries go
stale.

## staleness

entries decay silently. **reopen the original before**:

- quoting it exactly
- installing anything
- purchasing anything
- any consequential use

if an entry is more than a few months old and about to inform a real decision, say so and
re-read it.

## privacy

a url the user saves may reveal a great deal about them. the library is part of the knowledge
base and inherits its rules: it is not shared with third parties without explicit approval,
and urls containing tokens, session ids, or password-reset links are never stored — strip them
or refuse, and say which you did.

## pitfalls

- summarizing from the url or from prior knowledge instead of reading.
- storing a shortener or a tracking url as canonical.
- recording an install command you remembered rather than one the source documents.
- treating "saved" as "verified" or "endorsed".
- omitting the retrieval trigger, which turns the library into a graveyard.
- saving five near-duplicate entries for the same tool.
- keeping a url with an embedded credential or session token.

## verification checklist

- [ ] i opened the source, or the entry says explicitly that i could not
- [ ] the canonical url and access date are recorded
- [ ] purpose, useful-for, limits, and retrieval trigger are filled from what i read
- [ ] commands come from the source or are absent
- [ ] status reflects reality — `unverified` unless it was actually tried
- [ ] i searched the library before recommending anything
- [ ] no credential or session token is in the stored url
