import hashlib
import shutil
from pathlib import Path

import pytest

from algotrade.config import ConfigError, criteria_sha256, load_config, verify_criteria

ROOT = Path(__file__).resolve().parent.parent


def _copy(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    shutil.copytree(ROOT / "config", d)
    return d


def test_loads_both_markets():
    a, b = load_config("A"), load_config("B")
    assert a.instruments == ("SPY", "EFA", "IEF", "GLD", "DBC")
    assert b.instruments == ("BTCUSDT", "ETHUSDT")
    assert (a.periods_per_year, b.periods_per_year) == (252, 365)
    assert a.costs.slippage_rate == 0.001 and b.costs.commission_rate == 0.001
    assert a.thresholds.max_dd_max == 0.20 and b.thresholds.round_trips_min == 12
    assert a.end_date == "2026-09-30"
    assert a.data_dir == ROOT / "data"
    assert set(a.urls) == {"binance_vision", "binance_api", "stooq", "yahoo", "fred", "bcb_sgs"}


def test_criteria_sha256_pin_matches_the_file():
    cfg = load_config("A")
    raw = (ROOT / "docs" / "success-criteria.md").read_bytes().replace(b"\r\n", b"\n")
    assert cfg.criteria_sha256 == hashlib.sha256(raw).hexdigest()
    assert criteria_sha256() == cfg.criteria_sha256
    verify_criteria(cfg)


def test_verify_criteria_detects_a_changed_file(tmp_path):
    f = tmp_path / "c.md"
    f.write_bytes((ROOT / "docs" / "success-criteria.md").read_bytes() + b"\nedit\n")
    with pytest.raises(ConfigError, match="pinned"):
        verify_criteria(load_config("A"), f)


def test_crlf_is_normalised(tmp_path):
    raw = (ROOT / "docs" / "success-criteria.md").read_bytes().replace(b"\r\n", b"\n")
    f = tmp_path / "c.md"
    f.write_bytes(raw.replace(b"\n", b"\r\n"))
    verify_criteria(load_config("A"), f)


@pytest.mark.parametrize("fname,old,new", [
    ("common.toml", "[sim]\n", "[sim]\nsurprise = 1\n"),                 # unknown key
    ("common.toml", "[risk]", "[extra]\nx = 1\n\n[risk]"),               # unknown section
    ("A.toml", "[costs]", "[costs]\nbonus = 0.1"),                       # unknown key in the market file
    ("A.toml", 'sigma_target = 0.12', 'sigma_target = "0.12"'),          # wrong type
    ("common.toml", "variant_cap = 12", "variant_cap = true"),           # bool is not an int
    ("common.toml", 'end_date = "2026-09-30"', 'end_date = "30/09/2026"'),
    ("A.toml", 'name = "A"', 'name = "B"'),
])
def test_bad_config_is_an_error(tmp_path, fname, old, new):
    d = _copy(tmp_path)
    p = d / fname
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert old in text
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config("A", d)


def test_missing_key_and_missing_file_and_bad_market(tmp_path):
    d = _copy(tmp_path)
    p = d / "B.toml"
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    p.write_text("\n".join(l for l in text.split("\n") if not l.startswith("stale_after_days")), encoding="utf-8")
    with pytest.raises(ConfigError, match="missing key"):
        load_config("B", d)
    (d / "A.toml").unlink()
    with pytest.raises(ConfigError, match="not found"):
        load_config("A", d)
    with pytest.raises(ConfigError, match="unknown market"):
        load_config("C")


def test_invalid_toml(tmp_path):
    d = _copy(tmp_path)
    (d / "A.toml").write_text("this is = = not toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config("A", d)
