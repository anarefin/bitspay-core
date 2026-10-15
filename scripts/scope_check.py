#!/usr/bin/env python3
"""Service-scope guard: while .agent-scope names a service, nothing may change another services/<svc>/.

One rule, several callers (see docs/SERVICE-IMPLEMENTATION-STEPS.md):
  scope_check.py paths <path>...      exit 2 if any path is in another service (scripts/scope.sh check)
  scope_check.py staged               exit 1 if staged files touch another service (git pre-commit)
  scope_check.py claude-hook          Claude Code PreToolUse hook (stdin JSON; exit 2 blocks)
  scope_check.py cursor-pre-tool      Cursor preToolUse hook (stdin JSON; prints permission JSON)
  scope_check.py cursor-shell         Cursor beforeShellExecution hook
  scope_check.py cursor-after-edit    Cursor afterFileEdit hook (reverts an out-of-scope edit)
No .agent-scope -> everything is allowed.
"""
import json
import os
import re
import shlex
import subprocess
import sys

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LOCK = os.path.join(ROOT, ".agent-scope")
SERVICES = os.path.join(ROOT, "services")
CONTRACTS_VIEW = os.path.join(ROOT, ".contracts-view", "services")

# Bash: commands that only read. Anything else that names another service is treated as a write.
READ_ONLY = {"cat", "ls", "grep", "egrep", "rg", "find", "head", "tail", "wc", "less", "more", "diff",
             "file", "stat", "tree", "echo", "printf", "true", "jq", "sort", "uniq", "cut", "awk"}
READ_ONLY_GIT = {"diff", "log", "show", "status", "blame", "grep", "ls-files"}
WRITE_FLAGS = re.compile(r"(^|\s)(-i\b|-i\.|--in-place|-delete\b|-exec\b|-execdir\b|-ok\b|-fprint)")
SVC_IN_TEXT = re.compile(r"(?:^|[\s'\"=:(/.])(?:services|\.contracts-view/services)/(?:\d\d-)?([a-z0-9-]+-service)\b")


def locked():
    try:
        with open(LOCK) as f:
            svc = f.read().strip()
    except OSError:
        return None
    return svc or None


def service_of(path, cwd=None):
    """Service folder a path belongs to (after resolving symlinks), or None."""
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(cwd or os.getcwd(), p)
    real = os.path.realpath(p)
    for base, numbered in ((SERVICES, False), (CONTRACTS_VIEW, True)):
        rel = os.path.relpath(real, base)
        if rel == "." or rel.startswith(".."):
            continue
        name = rel.split(os.sep)[0]
        if numbered:  # broken/missing symlink in the contracts view: 03-wallet-service -> wallet-service
            name = re.sub(r"^\d\d-", "", name)
        return name
    return None


def foreign(paths, cwd=None):
    svc = locked()
    if not svc:
        return svc, []
    bad = []
    for p in paths:
        other = service_of(p, cwd)
        if other and other != svc:
            bad.append((p, other))
    return svc, bad


def message(svc, bad):
    lines = [f"Scope is locked to {svc}. These paths belong to another service and must not change:"]
    lines += [f"  - {p}  ({other})" for p, other in bad]
    lines.append("A change another service needs goes through /raise-cr. If you really are switching service, "
                 "the developer runs `make lock svc=<service>` (or `make unlock`).")
    return "\n".join(lines)


def _segments(cmd):
    return [s.strip() for s in re.split(r"\|\||&&|[|;&\n]", cmd) if s.strip()]


def bash_foreign(cmd, cwd=None):
    """Other services a shell command may write to (empty list if it only reads)."""
    svc = locked()
    if not svc:
        return svc, []
    named = set(SVC_IN_TEXT.findall(cmd))
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        tokens = cmd.split()
    for t in tokens:
        if "/" in t or t.startswith(".."):
            other = service_of(t.split("=", 1)[-1], cwd)
            if other:
                named.add(other)
    named.discard(svc)
    if not named:
        return svc, []
    stripped = re.sub(r"\d?>&\d|\d?>\s*/dev/null", "", cmd)
    writes = ">" in stripped or WRITE_FLAGS.search(stripped)
    if not writes:
        for seg in _segments(stripped):
            words = seg.split()
            while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):  # FOO=bar cmd
                words.pop(0)
            if not words:
                continue
            head = os.path.basename(words[0])
            if head == "git" and len(words) > 1 and words[1] in READ_ONLY_GIT:
                continue
            if head not in READ_ONLY:
                writes = True
                break
    return svc, sorted(named) if writes else []


def bash_message(svc, others):
    return (f"Scope is locked to {svc}. This command may change files of {', '.join(others)}, so it is blocked. "
            "Read-only commands (cat, ls, grep, git diff/log/show ...) are allowed. A change another service needs "
            "goes through /raise-cr; to switch service the developer runs `make lock svc=<service>`.")


def _stdin_json():
    try:
        return json.load(sys.stdin)
    except ValueError:
        return {}


def _input_paths(tool_input):
    keys = ("file_path", "notebook_path", "path", "target_file", "filePath", "targetFile", "target_notebook")
    return [tool_input[k] for k in keys if isinstance(tool_input.get(k), str)]


def claude_hook():
    data = _stdin_json()
    tool, ti, cwd = data.get("tool_name", ""), data.get("tool_input") or {}, data.get("cwd")
    if tool == "Bash":
        svc, others = bash_foreign(ti.get("command", ""), cwd)
        if others:
            print(bash_message(svc, others), file=sys.stderr)
            return 2
        return 0
    svc, bad = foreign(_input_paths(ti), cwd)
    if bad:
        print(message(svc, bad), file=sys.stderr)
        return 2
    return 0


def _cursor_reply(deny, text):
    reply = {"permission": "deny" if deny else "allow"}
    if deny:
        reply.update(user_message=text, agent_message=text)
    print(json.dumps(reply))
    return 0


def cursor_pre_tool():
    data = _stdin_json()
    ti = data.get("tool_input") or {}
    if isinstance(ti, str):
        try:
            ti = json.loads(ti)
        except ValueError:
            ti = {}
    if isinstance(ti.get("command"), str):
        svc, others = bash_foreign(ti["command"], data.get("cwd"))
        return _cursor_reply(bool(others), others and bash_message(svc, others))
    svc, bad = foreign(_input_paths(ti), data.get("cwd"))
    return _cursor_reply(bool(bad), bad and message(svc, bad))


def cursor_shell():
    data = _stdin_json()
    svc, others = bash_foreign(data.get("command", ""), data.get("cwd"))
    return _cursor_reply(bool(others), others and bash_message(svc, others))


def cursor_after_edit():
    data = _stdin_json()
    path = data.get("file_path", "")
    svc, bad = foreign([path]) if path else (None, [])
    if not bad:
        return 0
    tracked = subprocess.run(["git", "-C", ROOT, "ls-files", "--error-unmatch", path],
                             capture_output=True).returncode == 0
    if tracked:
        subprocess.run(["git", "-C", ROOT, "restore", "--", path], capture_output=True)
    elif os.path.isfile(path):
        os.remove(path)
    print(message(svc, bad) + "\nThe edit was reverted.", file=sys.stderr)
    return 0


def staged():
    out = subprocess.run(["git", "-C", ROOT, "diff", "--cached", "--name-only", "-z"],
                         capture_output=True, text=True, check=True).stdout
    svc, bad = foreign([os.path.join(ROOT, p) for p in out.split("\0") if p])
    if bad:
        bad = [(os.path.relpath(p, ROOT), o) for p, o in bad]
        print("pre-commit: " + message(svc, bad) + "\nUnstage them (git restore --staged <path>) or change the lock.",
              file=sys.stderr)
        return 1
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "paths":
        svc, bad = foreign(argv[2:])
        if bad:
            print(message(svc, bad), file=sys.stderr)
            return 2
        return 0
    handlers = {"staged": staged, "claude-hook": claude_hook, "cursor-pre-tool": cursor_pre_tool,
                "cursor-shell": cursor_shell, "cursor-after-edit": cursor_after_edit}
    if cmd in handlers:
        return handlers[cmd]()
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
