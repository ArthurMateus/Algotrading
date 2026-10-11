"""Hard rule 1: paper / backtest only. Fails if order-placing, signing or key-handling code appears."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE_DIRS = [ROOT / "src", ROOT / "tools"]

# Signing / wallet libraries and exchange trading SDKs.
FORBIDDEN_MODULES = ("eth_account", "eth_keys", "eth_keyfile", "coincurve", "ecdsa", "nacl", "web3", "solders",
                     "solana", "hyperliquid", "ccxt", "binance", "pybit", "alpaca", "alpaca_trade_api", "ib_insync",
                     "ib_async", "ibapi", "oandapyV20", "MetaTrader5", "cryptography", "hmac")
FORBIDDEN_IMPORT = re.compile(r"^\s*(?:import|from)\s+(" + "|".join(FORBIDDEN_MODULES) + r")\b")

# Order endpoints, signing calls and key material.
FORBIDDEN_TEXT = re.compile(
    r"private_key|privkey|secret_key|api_secret|mnemonic|seed_phrase|keypair|"
    r"sign_l1|sign_typed|sign_message|signTransaction|sendTransaction|"
    r"/exchange\b|/fapi/v\d+/order|/api/v3/order|/v5/order|/v2/orders|/v2/positions|"
    r"create_order|place_order|submit_order|cancel_order|"
    r"api-key|X-MBX-APIKEY|APCA-API-SECRET|os\.environ|getenv\(|dotenv|"
    r"Authorization|Bearer|method=\"(?:POST|PUT|DELETE|PATCH)\"|\bdata=", re.I)


def _code_files():
    for d in CODE_DIRS:
        if d.exists():
            yield from d.rglob("*.py")


def test_no_signing_or_trading_library_imports():
    for f in _code_files():
        for i, line in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
            assert not FORBIDDEN_IMPORT.search(line), f"{f.relative_to(ROOT)}:{i}: {line.strip()}"


def test_no_order_endpoints_signing_or_secrets():
    for f in _code_files():
        for i, line in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
            assert not FORBIDDEN_TEXT.search(line), f"{f.relative_to(ROOT)}:{i}: {line.strip()}"


def test_dependencies_have_no_trading_or_signing_sdk():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for mod in FORBIDDEN_MODULES:
        name = mod.lower().replace("_", "-")
        assert not re.search(rf'"{re.escape(name)}[\s<>=~!\[";]', text), f"pyproject.toml lists {mod}"


def test_lockfile_has_no_trading_or_signing_sdk():
    lock = ROOT / "uv.lock"
    names = set(re.findall(r'^name = "([^"]+)"', lock.read_text(encoding="utf-8"), re.M)) if lock.exists() else set()
    banned = {m.lower().replace("_", "-") for m in FORBIDDEN_MODULES}
    assert not names & banned, f"uv.lock pulls in {sorted(names & banned)}"


def test_only_sources_http_get_opens_urls():
    for f in _code_files():
        if f.name == "sources.py":
            continue
        text = f.read_text(encoding="utf-8-sig")
        assert not re.search(r"urlopen|http\.client|requests\.|httpx|socket\.", text), f"{f.relative_to(ROOT)} opens a connection"


def test_importing_the_package_loads_no_signing_library():
    code = ("import sys, pkgutil, importlib, algotrade\n"
            "for m in pkgutil.walk_packages(algotrade.__path__, 'algotrade.'):\n"
            "    importlib.import_module(m.name)\n"
            f"bad = [m for m in sys.modules if m.split('.')[0] in {FORBIDDEN_MODULES!r}]\n"
            "print(bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                         cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "SYSTEMROOT": "C:\\Windows"}).stdout
    assert out.strip() == "[]"
