# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"종착역이 없는 열차" (13-Fri): a Korean free-text train-mystery game built on a Flask chatbot base (hateslop 5-chatbot-base). Docs and UI strings are Korean. Player text is interpreted by a real OpenAI model; the **server decides** all game outcomes (items, clues, doors, puzzles, endings). There is no demo/mock mode at runtime (`DemoGenerator` is just the historical class name for the real OpenAI-backed generator).

## Commands

```powershell
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000 (PORT, FLASK_DEBUG=1 env vars)
python launch_game.py              # portable launcher (prompts for API key -> .env.local)
python -m unittest discover tests  # all tests; no API calls or cost
python -m unittest tests.test_smoke.<Class>.<test>   # single test
```

- Needs `OPENAI_API_KEY` (env or `.env`; optional `OPENAI_MODEL`, default `gpt-4o-mini`). `.env` must be kept byte-for-byte as provided — never rewrite it.
- `python tools/check_live_scenario.py --smoke` — opt-in QA against the real model and real routes (costs API calls; not run by unit tests).
- `tools/check_dialogue_ui.mjs`, `check_gameplay_ui.mjs` (with `dialogue_ui_server.py` / `gameplay_ui_server.py`) — browser UI checks.
- `tools/build_portable.py` builds the offline Windows ZIP (bundles `runtime/` embedded Python 3.11 + `public`, `templates`, `services`, `config`, `data`); `tools/verify_portable.py` checks an extracted bundle; `tools/clean_generated.py [--apply]` removes local QA profiles under `.local/`; `tools/optimize_png.py` shrinks art.
- `runtime/` and `dist/` are build artifacts (gitignored).

## Architecture

- `app.py`: Flask entry. Pages `/`, `/detail`, `/chat`; JSON API `/api/game`, `/api/game/new`, chat endpoint. Anonymous random game cookie (`train_game`), same-origin check on API POSTs, 16 KB body limit, errors as `{"error":{code,message}}` (`GameError`, `AIUnavailable` handlers). Supports Vercel (`VERCEL=1` changes static serving).
- `services/chatbot_service.py` (~2000 lines, the core): `GameStore` persists state, history and idempotent request results to SQLite (`data/train_state.sqlite3`) in one commit; `GameEngine` adjudicates location, ownership, inspection, dialogue, puzzles, endings; `ChatbotService` is the facade used by `app.py`. If the AI fails, the turn is not committed and the reservation is released. The "last chance" is consumed only at final confirmation.
- `services/generator.py`: all OpenAI calls. `interpret` turns the player's sentence into a structured intent via JSON Schema (action, target, negation, item identity, feature evidence); the generation step only picks an approved opening phrase for the NPC, and server-confirmed lines are concatenated verbatim — the model may not invent facts or answers.
- `services/retriever.py`: restricts knowledge to allowed `fact_id`s / characters / reveal conditions before generation (`data/knowledge/`).
- `services/character_dialogue.py`, `services/image_selector.py`: NPC dialogue data; backgrounds, character expressions and hotspot coordinates per location/door/flashlight state.
- `config/chatbot_config.json` (bot metadata) and `config/dialogue_scenario.json` (scenario).
- Frontend: `templates/` (index, detail, chat) + `public/assets/js/{chatbot,puzzles,audio}.js` + `css/`. UI clicks (select_npc, present, end_talk, operate, read_item) send `action` payloads to the same engine and are **not** re-interpreted by the AI. Request body is either `message` or `action`.

`docs/ARCHITECTURE.md`, `SCENARIO_COMPLIANCE.md`, `CHARACTER_SETTINGS.md` hold detailed rules; read them before changing game logic.

## Notes

- Tests mock the AI; keep them offline. `tests/test_portable_bundle.py` constrains which assets `build_portable.py` may omit (`SOURCE_ONLY_ASSETS`) — a new runtime reference to those images keeps them in the bundle.
- Project rule (from memory): never `git push` in this project.
