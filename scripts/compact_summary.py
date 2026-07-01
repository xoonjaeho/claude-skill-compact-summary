#!/usr/bin/env python3
"""/compact-summary — extract the current session's latest compaction summary to a file.

Claude Code compresses a long conversation (manual /compact or automatic auto-compact)
into a summary it stores as ONE line in the session transcript JSONL. This script finds
the CURRENT session's transcript, extracts the most recent compaction summary, writes it
to a file, and prints ONLY the file path plus a one-line meta.

Why a file, not stdout: a summary is ~10-20KB (~3-6k tokens). Re-printing it into the
chat spends those tokens as model output on every view. Writing it to disk and surfacing
just the path keeps viewing it near-free.

Discovery: the live session id is in $CLAUDE_CODE_SESSION_ID; the transcript is the
matching <id>.jsonl under ~/.claude/projects/*/ (globbing by filename avoids reproducing
Claude Code's cwd -> project-dir escaping). Fail closed: if the id is missing or the
transcript can't be uniquely located, error out rather than guess a different conversation.

    python compact_summary.py              # write the current session's latest summary
    python compact_summary.py --selftest   # verify extraction / normalization / meta logic
"""
import glob
import json
import os
import sys

PROJECTS = os.path.normpath(os.path.expanduser("~/.claude/projects"))
OUT_DIR = os.path.normpath(os.path.expanduser("~/.claude/compact-summaries"))


def find_transcript(session_id, projects_dir=PROJECTS):
    """Absolute path to the session's transcript JSONL; raise unless exactly one matches."""
    if not session_id:
        raise LookupError("CLAUDE_CODE_SESSION_ID is not set; cannot identify the current session.")
    matches = glob.glob(os.path.join(projects_dir, "*", session_id + ".jsonl"))
    if not matches:
        raise LookupError(f"no transcript found for session {session_id} under {projects_dir}")
    if len(matches) > 1:
        raise LookupError("more than one transcript matches this session id:\n  " + "\n  ".join(matches))
    return matches[0]


def normalize_content(content):
    """Flatten a transcript message's content (a string, or a list of parts) to plain text.

    Non-text parts (images, tool results) are dropped: only the summary prose is wanted.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content
                       if isinstance(p, dict) and p.get("type") == "text")
    return ""


def extract_summaries(lines):
    """Return compaction-summary texts from transcript lines, in file order.

    The authoritative test is the PARSED field ``isCompactSummary is True`` — never a raw
    substring match: an assistant message that quotes the field name would fool a substring
    scan, and a serializer that emits ``"isCompactSummary": true`` (space after the colon)
    would be missed by a no-space scan. A line that fails to parse is skipped — the final
    line of a live, still-being-written transcript can be a partial write, and a malformed
    non-summary line is irrelevant here anyway.
    """
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("isCompactSummary") is True:
            out.append(normalize_content(obj.get("message", {}).get("content")))
    return out


def estimate_tokens(text):
    """Rough token count (~4 chars/token heuristic); always label it ~ when shown."""
    return len(text) // 4


def write_summary(session_id, text, index, out_dir=OUT_DIR):
    """Write one summary to a deterministic, overwrite-in-place path; return the path.

    Named <id>-<index>.md so re-running overwrites rather than accumulating, and the file
    survives session-scratchpad cleanup (a viewer's output should still be there later).
    """
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{session_id}-{index}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main():
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    transcript = find_transcript(session_id)
    with open(transcript, encoding="utf-8") as f:
        summaries = extract_summaries(f)
    if not summaries:
        print("This session has not been compacted yet. (This views the current session "
              "only; summaries from earlier pre-/clear sessions are out of scope.)")
        return
    total = len(summaries)
    text = summaries[-1]
    path = write_summary(session_id, text, total)
    print(path)
    print(f"latest of {total} | {len(text):,} chars | ~{estimate_tokens(text):,} tokens "
          f"| excludes messages after this compaction")


def _selftest():
    import tempfile
    # normalize_content: string as-is; list keeps only text parts; anything else -> ""
    assert normalize_content("hello") == "hello"
    assert normalize_content([{"type": "text", "text": "a "},
                              {"type": "image", "x": 1},
                              {"type": "text", "text": "b"}]) == "a b"
    assert normalize_content(None) == "" and normalize_content(42) == ""
    # extract_summaries: parsed-field truth only, space-after-colon tolerated, partial line skipped
    lines = [
        json.dumps({"isCompactSummary": True, "message": {"content": "first"}}),   # compact json
        '{"isCompactSummary": true, "message": {"content": [{"type":"text","text":"sec"},'
        '{"type":"image","d":1},{"type":"text","text":"ond"}]}}',                   # spaced + list
        json.dumps({"type": "user", "message": {"content": "a normal turn"}}),      # no field
        json.dumps({"isCompactSummary": False, "message": {"content": "nope"}}),    # field is False
        '{"isCompactSummary": true, "message": {"content": "trunc',                 # partial final line
    ]
    got = extract_summaries(lines)
    assert got == ["first", "second"], f"expected two summaries in order, got {got!r}"
    # a decoy assistant line that merely mentions the field name must NOT be picked up
    decoy = json.dumps({"type": "assistant",
                        "message": {"content": [{"type": "text",
                                                 "text": 'the flag is "isCompactSummary":true'}]}})
    assert extract_summaries([decoy]) == [], "substring mention must not count as a summary"
    # estimate_tokens: ~4 chars/token
    assert estimate_tokens("x" * 40) == 10
    # find_transcript: exactly-one match required, else raises (fail closed)
    root = tempfile.mkdtemp()
    sid = "11111111-2222-3333-4444-555555555555"
    proj_a = os.path.join(root, "proj-a")
    os.makedirs(proj_a)
    open(os.path.join(proj_a, sid + ".jsonl"), "w").close()
    assert find_transcript(sid, root) == os.path.join(proj_a, sid + ".jsonl")
    try:
        find_transcript("", root); assert False, "empty id should raise"
    except LookupError:
        pass
    try:
        find_transcript("no-such-id", root); assert False, "missing transcript should raise"
    except LookupError:
        pass
    proj_b = os.path.join(root, "proj-b")   # same id under two project dirs -> ambiguous -> raise
    os.makedirs(proj_b)
    open(os.path.join(proj_b, sid + ".jsonl"), "w").close()
    try:
        find_transcript(sid, root); assert False, "ambiguous match should raise"
    except LookupError:
        pass
    # write_summary: utf-8 round-trip (summaries hold Korean / ₩) and deterministic overwrite path
    p1 = write_summary(sid, "요약 ₩7,600", 3, out_dir=root)
    assert p1.endswith(f"{sid}-3.md")
    with open(p1, encoding="utf-8") as fh:
        assert fh.read() == "요약 ₩7,600"
    assert write_summary(sid, "again", 3, out_dir=root) == p1, "same index overwrites same path"
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        try:
            main()
        except LookupError as e:
            print(f"compact-summary: {e}", file=sys.stderr)
            sys.exit(1)
