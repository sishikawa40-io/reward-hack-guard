"""role_guard.py と completion_gate.py が共有する設定読み込みとログ。"""
import json
import os
import tempfile
from fnmatch import fnmatch
from pathlib import Path

DEFAULT_CONFIG = {
    "roles": {
        # 親セッション（サブエージェント外）。既定では実装役と同じ扱いにする
        "main": {"deny_write": ["tests/*", "acceptance/*", ".claude/*"], "deny_read": ["acceptance/*"]},
        "implementer": {"deny_write": ["tests/*", "acceptance/*", ".claude/*"], "deny_read": ["acceptance/*"]},
        "test-writer": {"deny_write": ["src/*", ".claude/*"], "deny_read": []},
        "reviewer": {"deny_write": ["*"], "deny_read": []},
    },
    "gate": {
        "applies_to": ["main", "implementer"],
        "protected": ["tests/"],
        "test_cmd": None,
        "acceptance_cmd": None,
        "escalation_file": "ESCALATION.md",
        "max_blocks": 3,
    },
}


CONFIG_NAME = ".claude/reward-hack-guard.json"


def load_config(cwd: str) -> dict | None:
    """設定ファイルを読み、既定値に上書きして返す。設定ファイルがなければ None（何もしない）。

    探す順番：環境変数 GUARD_CONFIG → プロジェクトの .claude/reward-hack-guard.json。
    プラグインを入れただけでは動かず、設定ファイルを置いたプロジェクトでだけ有効になる（オプトイン）。
    """
    project = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    candidates = [os.environ.get("GUARD_CONFIG"), str(Path(project) / CONFIG_NAME)]
    path = next((Path(c) for c in candidates if c and Path(c).exists()), None)
    if path is None:
        return None
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    user = json.loads(path.read_text())
    cfg["roles"].update(user.get("roles", {}))
    cfg["gate"].update(user.get("gate", {}))
    return cfg


def state_dir(session_id: str) -> Path:
    base = os.environ.get("GUARD_STATE_DIR") or str(Path(tempfile.gettempdir()) / f"claude-guard-{session_id or 'nosession'}")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def log(session_id: str, record: dict) -> None:
    with open(state_dir(session_id) / "guard.log", "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def rel_path(path: str, cwd: str) -> str:
    """ツール入力のパスを、プロジェクトからの相対パス（/ 区切り）にする。外側なら絶対パスのまま。"""
    p = Path(path)
    if not p.is_absolute():
        p = Path(cwd) / p
    try:
        return p.resolve().relative_to(Path(cwd).resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def matches(rel: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        if fnmatch(rel, pat):
            return pat
    return None
