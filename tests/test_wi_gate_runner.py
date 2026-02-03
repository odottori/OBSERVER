# -*- coding: utf-8 -*-
import sys
import types
from pathlib import Path


def _add_scripts_to_path():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return root, scripts


def test_gate_passes_profile_and_fail_on_hits_by_default(tmp_path: Path, monkeypatch):
    _add_scripts_to_path()
    import wi_gate_runner

    captured = {}

    # Stub wi_log_collector module used inside wi_gate_runner.run_gate()
    fake = types.SimpleNamespace()

    def fake_main(argv):
        captured["argv"] = list(argv)
        return 0

    fake.main = fake_main

    sys.modules["wi_log_collector"] = fake  # ensure import inside run_gate gets the stub

    rc = wi_gate_runner.main(
        [
            "--wi",
            "WI-0260",
            "--mode",
            "normal",
            "--reports-dir",
            str(tmp_path / "reports"),
            "--dry-run",
        ]
    )
    assert rc == 0
    argv = captured.get("argv", [])
    assert "--profile" in argv
    # default profile is hardfail
    assert argv[argv.index("--profile") + 1] == "hardfail"
    assert "--fail-on-hits" in argv
