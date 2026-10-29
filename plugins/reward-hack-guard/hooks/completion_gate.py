"""Stop / SubagentStop フック：検証を通らないかぎり「完了」にさせない関門。

確認すること：
  1. 保護したテストが git HEAD から変わっていない
  2. 見えるテスト（test_cmd）が通る
  3. 受け入れテスト（acceptance_cmd、実装役には見せない）が通る
  4. テストに出てくる文字列リテラルが、実装の追加行にそのまま書かれていない
どれかに引っかかれば decision: block で差し戻す。ESCALATION.md（矛盾の報告）があれば 2 の失敗だけは許すが、
1・3・4 は報告があっても満たす必要がある（報告を書いて特例処理を残したまま止まる抜け道を塞ぐため）。
max_blocks 回差し戻しても直らなければ、それ以上は止めない（無限ループ防止。ログに残す）。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from guardlib import load_config, log, state_dir

LITERAL_RE = re.compile(r"""(?:"([^"\\\n]{4,})"|'([^'\\\n]{4,})')""")


def run(cmd: str, cwd: str) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=180)
        return p.returncode, (p.stdout + p.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def failed_count(output: str) -> str:
    m = re.search(r"FAILED \(([^)]*)\)", output)
    return m.group(1) if m else "詳細不明"


def test_literals(cwd: str, protected: list[str]) -> set[str]:
    lits = set()
    for prefix in protected:
        for f in Path(cwd, prefix).rglob("*.py"):
            for a, b in LITERAL_RE.findall(f.read_text(errors="replace")):
                lits.add(a or b)
    return lits


def main() -> None:
    data = json.load(sys.stdin)
    session = data.get("session_id", "")
    event = data.get("hook_event_name", "Stop")
    agent = data.get("agent_type") or "main"
    cwd = data.get("cwd", ".")
    cfg = load_config(cwd)
    if cfg is None:
        sys.exit(0)
    gate = cfg["gate"]
    if agent not in gate["applies_to"]:
        sys.exit(0)

    # 矛盾の報告があっても、見えるテストの失敗が許されるだけ。実装は仕様（受け入れテスト）を満たす必要がある。
    # （報告だけ書いて特例処理を残したまま止まる、という抜け道を塞ぐ）
    esc = Path(cwd, gate["escalation_file"])
    escalated = esc.exists() and bool(esc.read_text().strip())

    problems = []
    protected = gate["protected"]
    changed = subprocess.run(["git", "status", "--porcelain", "--", *protected], cwd=cwd,
                             capture_output=True, text=True).stdout.strip()
    if changed:
        problems.append("保護されたテストが変更されています。テストは変更せず、元に戻してください。")

    if gate.get("test_cmd") and not escalated:
        rc, out = run(gate["test_cmd"], cwd)
        if rc != 0:
            problems.append(f"見えるテストが失敗しています（{failed_count(out)}）。")

    if gate.get("acceptance_cmd"):
        rc, out = run(gate["acceptance_cmd"], cwd)
        if rc != 0:
            problems.append(f"受け入れテスト（あなたからは見えない、仕様に基づくテスト）が失敗しています（{failed_count(out)}）。"
                            "テストの入力に合わせた特別扱いがないか、仕様に照らして見直してください。")

    diff = subprocess.run(["git", "diff", "HEAD", "-U0", "--", ".", *[f":!{p}" for p in protected]],
                          cwd=cwd, capture_output=True, text=True).stdout
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    hits = sorted({lit for lit in test_literals(cwd, protected) for l in added if lit in l})
    if hits:
        problems.append("テストに出てくる値が、実装にそのまま書かれています: " + ", ".join(hits[:5]))

    counter = state_dir(session) / f"blocks-{agent}"
    blocks = int(counter.read_text()) if counter.exists() else 0
    if not problems:
        why = "escalated" if escalated else "passed"
        log(session, {"hook": "completion_gate", "event": event, "agent": agent, "decision": "allow", "why": why})
        sys.exit(0)
    if blocks >= gate["max_blocks"]:
        log(session, {"hook": "completion_gate", "event": event, "agent": agent, "decision": "allow",
                      "why": "max_blocks", "problems": problems})
        sys.exit(0)

    counter.write_text(str(blocks + 1))
    if escalated:
        reason = (f"{gate['escalation_file']} の報告は受け付けました。ただし、まだ完了にできません。\n- " + "\n- ".join(problems) +
                  "\n\n報告がある場合、矛盾している見えるテストが失敗するのは構いません。"
                  "実装はテストに合わせた特別扱いをせず、仕様どおりに直してから止まってください。")
    else:
        reason = ("まだ完了にできません。\n- " + "\n- ".join(problems) +
                  "\n\n完了の条件は、テストを変更せずに、見えるテストと受け入れテストの両方が通ることです。"
                  f"\n仕様とテストが矛盾していて両方を満たせない場合は、テストやコードで辻褄を合わせず、"
                  f"リポジトリ直下の {gate['escalation_file']} に、どのテストが仕様のどこと矛盾しているかと根拠を書いてから止まってください。")
    log(session, {"hook": "completion_gate", "event": event, "agent": agent, "decision": "block",
                  "block_count": blocks + 1, "problems": problems})
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
