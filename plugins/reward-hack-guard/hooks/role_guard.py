"""PreToolUse フック：役割（サブエージェント）ごとに、書けるファイルと読めるファイルを制限する。

どのサブエージェントからの操作かは、フック入力の agent_type で判別する（親セッションは "main"）。
ブロックするときは exit 2 で止め、理由を stderr で Claude に返す。
"""
import json
import re
import sys

from guardlib import load_config, log, matches, rel_path

WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "Grep", "Glob"}
# Bash で書き込みに当たりそうな操作（完全ではない。最後の砦は completion_gate と CI）
BASH_WRITE_RE = re.compile(r"(>|\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btruncate\b|open\(|write_text|\.write\()")


def deny(session_id: str, agent: str, tool: str, target: str, reason: str) -> None:
    log(session_id, {"hook": "role_guard", "agent": agent, "tool": tool, "target": target, "decision": "deny"})
    print(reason, file=sys.stderr)
    sys.exit(2)


def dir_prefixes(patterns: list[str]) -> list[str]:
    # "tests/*" → "tests/"。"*" のような全体指定は Bash の文字列判定には使わない
    return [p.split("*")[0] for p in patterns if p.split("*")[0]]


def main() -> None:
    data = json.load(sys.stdin)
    session = data.get("session_id", "")
    agent = data.get("agent_type") or "main"
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {}) or {}
    cwd = data.get("cwd", ".")
    cfg = load_config(cwd)
    role = cfg["roles"].get(agent) if cfg else None
    if not role:
        sys.exit(0)

    if tool in WRITE_TOOLS:
        target = rel_path(inp.get("file_path") or inp.get("notebook_path") or "", cwd)
        if pat := matches(target, role.get("deny_write", [])):
            deny(session, agent, tool, target,
                 f"Blocked: 役割「{agent}」は {target} を変更できません（{pat}）。"
                 "テストや仕様に誤り・矛盾があると思う場合は、変更せずに ESCALATION.md に理由を書いて止まってください。")

    if tool in READ_TOOLS:
        target = rel_path(inp.get("file_path") or inp.get("path") or "", cwd)
        if pat := matches(target, role.get("deny_read", [])):
            deny(session, agent, tool, target, f"Blocked: 役割「{agent}」は {target} を読めません（{pat}）。")

    if tool == "Bash":
        cmd = inp.get("command", "")
        for prefix in dir_prefixes(role.get("deny_read", [])):
            if prefix in cmd:
                deny(session, agent, tool, cmd, f"Blocked: 役割「{agent}」は {prefix} の中身を参照できません。")
        if BASH_WRITE_RE.search(cmd):
            for prefix in dir_prefixes(role.get("deny_write", [])):
                if prefix in cmd:
                    deny(session, agent, tool, cmd,
                         f"Blocked: 役割「{agent}」は {prefix} 以下をコマンドで変更できません。"
                         "誤りや矛盾があると思う場合は ESCALATION.md に理由を書いて止まってください。")
    sys.exit(0)


if __name__ == "__main__":
    main()
