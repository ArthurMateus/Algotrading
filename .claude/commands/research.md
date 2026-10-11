---
description: Phase 1 - research strategies and markets, then score candidates; stops at HUMAN GATE 1
argument-hint: "[optional focus, e.g. 'redo market survey for FX only']"
---
Run phase 1 of the pipeline in `CLAUDE.md`. Focus from the owner (may be empty): $ARGUMENTS

1. Read `CLAUDE.md` and `context.md`.
2. Launch the `strategy-researcher` and `market-researcher` agents IN PARALLEL (one message, two Agent calls). Tell
   each its output file (`docs/strategy-survey.md`, `docs/market-survey.md`), today's date, and any owner answers
   recorded in `context.md` (country, capital, horizon). If a focus is given, only redo what it names.
3. When both are done, check each report: sources present, under ~1,500 words, evidence vs opinion separated. Send
   it back to its agent if not.
4. Launch `quant-economist` for `docs/candidates.md` (phase 1 section of its prompt).
5. Update `context.md`, run `uv run pytest`, and commit the docs (stage explicit paths).
6. HUMAN GATE 1: show the owner the comparison matrix, the top candidates and the recommendation; ask which one to
   build (or for more research) and for their country, starting capital and time horizon. Then STOP and wait.
