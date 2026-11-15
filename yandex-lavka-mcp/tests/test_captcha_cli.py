import runpy
import sys
from pathlib import Path

import pytest


@pytest.fixture
def helper():
    script = Path(__file__).resolve().parents[1] / "scripts" / "solve_captcha.py"
    if not script.is_file():  # The Compose suite lives separately from the packaged source.
        script = Path("/sources/lavka/scripts/solve_captcha.py")
    return runpy.run_path(str(script))


def test_help_and_missing_dependency(helper, monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    monkeypatch.setattr(sys, "argv", ["solve_captcha.py", "--help"])
    with pytest.raises(SystemExit) as exc:
        helper["main"]()
    assert exc.value.code == 0 and "--output" in capsys.readouterr().out
    path = tmp_path / "result"
    monkeypatch.setattr(sys, "argv", ["solve_captcha.py", "--proxy", "unused", "--output", str(path)])
    assert helper["main"]() != 0 and not path.exists()
    assert "requires Playwright" in capsys.readouterr().err


def test_result_is_private_and_never_overwritten(helper, tmp_path, capsys):
    path = tmp_path / "result"
    helper["save_result"](path, "fixture-first")
    with pytest.raises(FileExistsError):
        helper["save_result"](path, "fixture-second")
    assert path.read_text() == "fixture-first"
    if sys.platform != "win32":
        assert path.stat().st_mode & 0o077 == 0
    assert capsys.readouterr() == ("", "")
