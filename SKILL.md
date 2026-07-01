---
name: compact-summary
description: View the current Claude Code session's compaction summary — the text produced when the conversation is compressed by manual /compact or automatic auto-compact — WITHOUT re-printing it into the chat. A summary is ~10-20KB (~3-6k tokens), so the skill extracts it to a file and returns only the path plus a one-line meta; it never echoes the body. Use when the user asks to see, read, or check what the last compaction summarized. Views the current session only.
---

# /compact-summary — view this session's compaction summary (as a file path)

A compaction summary lives as one line in the session transcript and is not re-viewable in
the TUI. This skill extracts the current session's latest summary to a file and hands back
the path — printing the ~4k-token body into chat would waste exactly what the skill exists
to avoid.

## Steps (run on invocation)

1. Run the script:
   ```
   python ~/.claude/skills/compact-summary/scripts/compact_summary.py
   ```
2. Relay the script's stdout **verbatim** — the file path and the one-line meta. That is the
   whole deliverable.

## Hard rules

- **Never open the output file.** Do not `Read`, `cat`, or otherwise load the written file,
  and never quote or summarize the summary body in chat — that re-imports the ~4k tokens the
  skill is built to save. The user opens the file themselves.
- **Report only what the script prints** — path + meta. The meta (compaction number, size)
  is computed by the script, so you never need to read the file to describe it.
- **Current session only.** The script targets `$CLAUDE_CODE_SESSION_ID`. If it prints "not
  compacted yet", relay that as-is — do not go hunting other sessions' transcripts.
- If the script exits with an error (no session id / transcript not uniquely found), relay
  the error line; do not fall back to guessing a different conversation.
