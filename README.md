# /compact-summary — view a session's compaction summary

A Claude Code skill that surfaces the **compaction summary** of the current session — the
text Claude Code generates when it compresses a long conversation, whether you ran `/compact`
manually or auto-compact fired on its own.

The catch it solves: that summary is stored as a single line in the session transcript and
Claude Code does **not** let you re-read it in the TUI (compaction prints only a
`Conversation compacted` line). Asking the assistant to reprint it costs ~3-6k output tokens
every time — a summary measures ~10-20KB. So this skill extracts the summary to a file and
returns **only the file path plus a one-line meta**; the body never re-enters the chat.

## Quick start

```
/compact-summary
```

Output is two lines — a path and a meta line:

```
C:\Users\you\.claude\compact-summaries\236219d3-...-2.md
latest of 2 | 14,821 chars | ~4,234 tokens | excludes messages after this compaction
```

Open that file to read the summary. Nothing is printed into the conversation.

## What it shows (and what it does not)

The summary is the compressed stand-in for the conversation *before* the compaction point.
It is **not** the session's full current context: the live context also holds the system
prompt, your `CLAUDE.md`/memory, and every turn *after* the compaction — none of which are in
this file. Hence the meta's `excludes messages after this compaction`.

If a long session compacted more than once, each compaction is its own summary line; this
skill writes the **latest** one and reports `latest of N` so you know earlier ones exist.

## How it works

```
[invocation]  /compact-summary
   └─ Claude runs scripts/compact_summary.py and relays its stdout verbatim

[script]
   session id = $CLAUDE_CODE_SESSION_ID
   transcript = the one  ~/.claude/projects/*/<id>.jsonl  matching that id   (else: fail closed)
   summaries  = every transcript line where the PARSED field isCompactSummary is True
   none?  -> print "not compacted yet", write nothing, exit 0
   else   -> write the LAST summary to ~/.claude/compact-summaries/<id>-<N>.md
             print: path + "latest of N | chars | ~tokens | excludes post-compaction messages"
```

Design choices that matter:

- **Discovery by session id, not mtime.** The live id is in `$CLAUDE_CODE_SESSION_ID`;
  globbing `~/.claude/projects/*/<id>.jsonl` by filename sidesteps having to reproduce Claude
  Code's cwd→project-dir escaping. An mtime "newest file" fallback is deliberately **omitted**
  — it could silently pick a different project's conversation. If the id is unset or the file
  isn't uniquely found, the script errors instead of guessing.
- **Parsed field, never a substring.** Lines are matched by `json.loads(...)["isCompactSummary"]
  is True`. A raw substring scan would be fooled by an assistant message quoting the field name
  and would miss a `"isCompactSummary": true` written with a space after the colon.
- **Tolerates a live transcript.** The current session's file is still being appended to, so a
  truncated final line is expected; the parser skips unparseable lines rather than aborting.
- **Meta is script-computed.** Char/token counts come from the script, so the assistant never
  needs to open the file to describe it — preserving the token saving end to end.

## Files

```
compact-summary/
├── README.md    this file
├── LICENSE      MIT
├── SKILL.md     skill body Claude follows at runtime (run the script, relay stdout, never open the file)
└── scripts/
    └── compact_summary.py   locate transcript, extract latest summary, write file, print path + meta
```

Output lives outside the skill, at `~/.claude/compact-summaries/<session-id>-<N>.md`. Files
are overwritten in place per (session, compaction number), so re-running never accumulates
copies. They persist until you delete them (the original transcript keeps its own copy
regardless).

## Install

Copy this directory to `~/.claude/skills/compact-summary/`:

```bash
git clone <this-repo> ~/.claude/skills/compact-summary
```

The directory name `compact-summary` is significant — it must match the slash command
(`/compact-summary`). No hook and no settings change is needed; the skill is invoked on demand.

## Verify

```
python ~/.claude/skills/compact-summary/scripts/compact_summary.py --selftest
```

Expect `selftest ok` (checks parsed-field extraction, space-after-colon tolerance, list-content
normalization, partial-line skipping, fail-closed transcript lookup, and utf-8 round-trip). For
a live check, run `/compact-summary` in a session that has compacted and open the printed path.

## Limits / out-of-scope

- **Current session only** — targets `$CLAUDE_CODE_SESSION_ID`. Viewing an arbitrary past
  session, or a summary from before a `/clear`, is out of scope.
- **The summary, not the live context** — for a real-time breakdown of what the context
  currently holds, use Claude Code's built-in `/context`.
- **Latest by default** — selecting an earlier compaction by index is not implemented (the
  meta reports how many exist); add a `--index N` flag if that becomes necessary.

## Dependencies

- Python 3.9+ (standard library only — no third-party packages)
- A Claude Code build that sets `CLAUDE_CODE_SESSION_ID` and stores per-session JSONL
  transcripts under `~/.claude/projects/`

## License

MIT — see [LICENSE](LICENSE).
