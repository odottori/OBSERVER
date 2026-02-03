# -*- coding: utf-8 -*-
import sys
from pathlib import Path

import pytest


def _add_scripts_to_path():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return root, scripts


def _write_all_expected(tmp_reports: Path, wi: str, mode: str):
    # Import after path injection
    import wi_log_collector

    expected = wi_log_collector._expected_files(wi, mode, tmp_reports)
    for gate, path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Minimal non-empty content
        path.write_text(f"{gate}: ok\n", encoding="utf-8")


def test_collect_hardfail_skips_cmd_lines(tmp_path: Path):
    _add_scripts_to_path()
    import wi_log_collector

    wi = "WI-0260"
    reports = tmp_path / "reports"
    _write_all_expected(reports, wi, "normal")

    # Inject a line that would have been a false-positive if scanned.
    pytest_log = reports / f"pytest_{wi}.log"
    pytest_log.write_text(
        "CMD: py -m pytest -q -W error::DeprecationWarning\nALL GOOD\n",
        encoding="utf-8",
    )

    rc, checks = wi_log_collector.collect(
        wi=wi,
        mode="normal",
        reports_dir=reports,
        patterns=wi_log_collector.PROFILE_PATTERNS["hardfail"],
        max_hits_per_file=25,
        fail_on_hits=True,
    )
    assert rc == 0
    assert sum(len(c.hits) for c in checks) == 0


def test_collect_hardfail_hits_fail_when_enabled(tmp_path: Path):
    _add_scripts_to_path()
    import wi_log_collector

    wi = "WI-0260"
    reports = tmp_path / "reports"
    _write_all_expected(reports, wi, "normal")

    bad_log = reports / f"pytest_{wi}.log"
    bad_log.write_text("Traceback (most recent call last):\n", encoding="utf-8")

    rc, checks = wi_log_collector.collect(
        wi=wi,
        mode="normal",
        reports_dir=reports,
        patterns=wi_log_collector.PROFILE_PATTERNS["hardfail"],
        max_hits_per_file=25,
        fail_on_hits=True,
    )
    assert rc == 3
    assert sum(len(c.hits) for c in checks) >= 1


def test_collect_profile_none_never_hits(tmp_path: Path):
    _add_scripts_to_path()
    import wi_log_collector

    wi = "WI-0260"
    reports = tmp_path / "reports"
    _write_all_expected(reports, wi, "normal")

    bad_log = reports / f"pytest_{wi}.log"
    bad_log.write_text("Traceback (most recent call last):\n", encoding="utf-8")

    rc, checks = wi_log_collector.collect(
        wi=wi,
        mode="normal",
        reports_dir=reports,
        patterns=(),
        max_hits_per_file=25,
        fail_on_hits=True,
    )
    assert rc == 0
    assert sum(len(c.hits) for c in checks) == 0
