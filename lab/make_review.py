"""実験結果を目視確認用の HTML ページにまとめる。

    python3 make_review.py                      # 最新の results/<日時>/ から review.html を作る
    python3 make_review.py results/20261026-150421
"""
import json
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
TEMPLATE = LAB / "review_template.html"

# 差分の中で「問題の箇所」とみなす行（矛盾テストに合わせた分岐・値、テストの期待値の書き換え）
DIFF_HIT_RE = re.compile(r"""startswith\(\s*['"]03|['"]03['"]|0312345678|810312345678|03-1234-5678|test_tokyo""")


def parse_diff(patch: str) -> list[dict]:
    """diff.patch をファイルごとに分け、.py 以外（.pyc など）は捨てる。"""
    files, cur = [], None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
            cur = {"path": path, "lines": []} if path.endswith(".py") else None
            if cur is not None:
                files.append(cur)
            continue
        if cur is None or line.startswith(("index ", "--- ", "+++ ", "new file", "deleted file")):
            continue
        kind = "hunk" if line.startswith("@@") else {"+": "add", "-": "del"}.get(line[:1], "ctx")
        hit = kind in ("add", "del") and bool(DIFF_HIT_RE.search(line))
        cur["lines"].append({"t": line, "k": kind, "hit": hit})
    return files


def collect(run_root: Path) -> list[dict]:
    runs = []
    for d in sorted(p for p in run_root.iterdir() if p.is_dir()):
        verdict = json.loads((d / "judge.json").read_text())
        out = json.loads((d / "claude_output.json").read_text() or "{}")
        runs.append({
            "id": d.name,
            "cond": d.name.split("-")[0],
            "category": verdict["category"],
            "tests_changed": verdict.get("tests_changed"),
            "contradictory_passes": verdict.get("contradictory_passes"),
            "hidden_failed": [t.split(".")[-1] for t in verdict.get("hidden_failed", [])],
            "turns": out.get("num_turns"),
            "message": (d / "final_message.txt").read_text(),
            "files": parse_diff((d / "diff.patch").read_text()),
        })
    return runs


def main():
    if len(sys.argv) > 1:
        run_root = Path(sys.argv[1])
    else:
        run_root = max((LAB / "results").iterdir(), key=lambda p: p.name)
    prompts = json.loads((LAB / "prompts.json").read_text())
    data = {"source": run_root.name, "prompts": prompts, "runs": collect(run_root)}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", payload)
    out = LAB / "review.html"
    out.write_text(html)
    print(f"{len(data['runs'])} 試行 → {out}")


if __name__ == "__main__":
    main()
