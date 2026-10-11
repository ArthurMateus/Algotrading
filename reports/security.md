# Security review (2026-10-11)

Reviewer: security-reviewer agent (read-only). Scope: every module in `src/algotrade/`, `tools/record_fixtures.py`,
`tests/test_safety.py`, `pyproject.toml`, `uv.lock`, `.gitignore`, `reports/`, and the full public git history
(`git log -p --all`, 19 commits at review time). `.env` and `secrets/` were not opened, and neither exists.

## Verdict: PASS
No secrets, personal data, authenticated or write network calls, or order/signing paths were found in the tree or
in the public history. There are no critical, high or medium findings.

## Findings (all low; status after the orchestrator's follow-up)
1. `sources.http_get` accepted plain `http://`. **Fixed:** it is now https only, with plain http allowed only for
   the loopback test server (`src/algotrade/sources.py`).
2. `tests/test_safety.py` did not forbid POST/PUT/DELETE, `data=` bodies, or `Authorization`/`Bearer` headers, and
   did not check that `sources.http_get` is the only place that opens a URL. **Fixed:** patterns added, plus
   `test_only_sources_http_get_opens_urls`. A planted POST with an auth header now fails three safety tests.
3. The dependency check read only `pyproject.toml`. **Fixed:** `test_lockfile_has_no_trading_or_signing_sdk`
   checks `uv.lock` too.
4. `.hypothesis/` was not git-ignored. **Fixed:** `.gitignore` now also covers `.hypothesis/`, `*.pem`, `*.key`
   and `*.log`.
5. Informational: `evaluate.py` runs `git rev-parse` / `git status` with a fixed argument list and no shell.
6. Informational: the commit author email is a placeholder (`your-email@example.com`), so no real email is
   published.

## Evidence summary
- **Network:** one primitive (`sources.http_get`, GET only, fixed User-Agent, no auth). The hosts are
  data.binance.vision, data-api.binance.vision (public exchangeInfo), stooq.com, query1.finance.yahoo.com,
  fred.stlouisfed.org and api.bcb.gov.br, all from `config/common.toml`.
- **Orders:** there is no broker adapter. `broker.py` is a simulated fill and cost model with no I/O. The paper
  step writes only local files.
- **Dependencies:** 16 packages, all benign (numpy, pandas, pyarrow and their deps; pytest and hypothesis for dev).
  `uv.lock` is hash-pinned to pypi.org.
- **Reports:** published results contain only public-market metrics; no account, credential or personal data.
