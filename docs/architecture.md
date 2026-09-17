# Architecture

## Request path

`browser → WSGI Application → Api → Game → ModelService → provider`

| File | Responsibility |
| --- | --- |
| `server/wsgi.py` | Host/origin checks, proxy address, HTTP errors |
| `server/api.py` | Routes, JSON, cookies, quotas and nonblocking session lock |
| `server/router.py` | Local threaded WSGI server; Gunicorn uses the same application |
| `server/static.py` | Local assets and browser security headers |
| `engine/game.py` | Chat/edit/regenerate, vault checks, progression, resets, public state |
| `engine/models.py` | Provider selection, credentials, call limits, model invocation |
| `engine/session_store.py` | RAM sessions, expiry, capacity and state transitions |
| `engine/limits.py` | Request and model-call allowances; concurrency slots |
| `engine/providers/` | Provider-specific HTTP/SDK mapping and safe error handling |
| `engine/pipeline.py` | Ordered input/output defenses selected by the floor |
| `engine/settings.py` | Validated environment configuration |
| `web/app.js` | User actions and server-state refresh |
| `web/provider-setup.js` | Local API-key/model dialog |
| `web/*-view.js` | Floor and conversation rendering |
| `web/api.js` | Fetch and server-error handling |
| `web/wards.js` | Room fittings and reactions to server block events |

The browser uses native ES modules; no bundler or CDN. Model defaults come from
`engine/providers/registry.py`, floor availability from `config/floors.json`.
Artwork/copy overrides live in `web/floor-visuals.js`; styling is in `web/app.css`.

## Contracts to preserve

- `Api.dispatch` holds the session lock across each operation, including model
  calls. Concurrent requests for that game return `409 game_busy`; other games
  continue. Direct callers of `Game` must hold the same lock.
- Chat history changes only after the provider and output defenses succeed.
  Failed edits/regenerations preserve the last completed exchange.
- The vault code is synthetic, per-session and server-owned. Only code submission
  can mark a floor cleared. A model reply that leaks the code is intentional on
  the early floors; do not add a global secret filter.
- `POST /api/floor/select` accepts `{ "floor": 1 }` through floor 9 without an
  unlock requirement. Revisiting restores that room's code and conversation.
  Reset affects only the active room. Selecting a room does not mark others
  cleared or skipped; the skip action records uncleared playable floors separately.
- Preview floors expose an opening message and artwork. Chat/edit/regenerate and
  code submission return `409 floor_not_ready` before any model call or win.
- Provider credentials live outside game state. Never log keys, prompts,
  conversations, cookies or model response bodies.
- One process/worker and one application instance while state is in RAM. The session store
  removes local provider keys on expiry. Resets do not reset request allowances.
- Anonymous limits apply to session and network, not verified people. Cookie
  copying shares a game. Network hashes and limits reset on server restart.
- Trust forwarded IPs only from explicitly configured proxy networks. The proxy
  must append the client IP without a port; prevent direct access around it.

## Add or change a floor

Follow the [intended progression](progression.md) for each floor's purpose and
the distinction between playable challenges and previews.

1. Edit `config/floors.json`: contiguous numbers, cumulative protection names.
   Use unique slugs and JSON booleans for `implemented`. All rooms are accessible
   regardless of this flag; preview rooms do not lock later challenges.
2. Add `config/prompts/floor-NN.json` with `warden_name`, `system_prompt` and
   `opening_message`. The floor prompt contains `{vault_code}` exactly once.
   A preview needs only `warden_name` and `opening_message`; no system prompt runs.
3. Add runtime defenses under `engine/middleware/` and register their factories
   in `engine/pipeline.py`. A defense implements `before(context)` and
   `after(context)`, mutating model messages/reply or raising a safe `RequestError`.
   Both stages run in the floor's declared order; each request gets fresh instances.
4. Add presentation overrides in `web/floor-visuals.js`, then set `implemented`
   to true. Test inherited behavior, blocked input/output, retries and progression.

### Implemented defenses

Each floor retains all previous protections. The registry in `pipeline.py` maps
protection names to fresh per-request objects in `engine/middleware/`.

| Floor | Added behavior |
| --- | --- |
| 1 | Prompt secrecy rule |
| 2 | Prompt authority boundary (the Codex) |
| 3 | NFKC Unicode normalization, removal of format controls, whitespace normalization; bounded English patterns for direct disclosure, instruction overrides, authority claims and role delimiters |
| 4 | Case-insensitive literal code check on the full model reply |
| 5 | Complete-code checks after separator removal, normalization, and up to two HTML/URL/Unicode-escape decoding passes; reversed text, ROT13, Base64, hex, decimal and binary ASCII representations |

The input layer checks all user messages in the candidate conversation, including
edit/regenerate paths; it leaves trusted system text and assistant history alone.
The model receives normalized input, while stored history preserves the player's
original text. Input blocks happen before a model call. Output blocks happen
before committing history. Both return HTTP 422 with a safe `input_blocked` or
`output_blocked` notice plus a `defense` identifier; a blocked reply is never
returned, saved or logged. `web/wards.js` uses that identifier to animate only
the matching thorn ward, brass seal or prism.

These deliberately limited rules are not semantic classifiers. Floor 3 permits
novel paraphrases and other languages. Floor 4 permits disguised codes. Floor 5
still permits semantic clues, fragments across replies, unknown encodings, and
transformations beyond its decoding budget. Encoded-spelling checks cover upper,
lower and title case; complete Base64 tokens are also decoded. These boundaries
are part of the game, not promises of production secret protection.

Unknown protection names on an implemented floor fail startup. Floors 6–9 stay
previews until their protections and full prompts are implemented. Their room
greetings say so; their fittings do not react to attempts.

Visual families are Sprouts (1–3), Sentinels (4–7), and Sovereigns (8–9).
Atlas and Aurum each have their own guardian and room artwork. Tier defaults and
per-floor overrides live in `web/floor-visuals.js`; local SVGs are in `web/assets/`.
Room fittings share the door's 620×650 SVG canvas. Their coordinates and brief
block reactions live in `web/wards.js`; they have no controls or explanation panels.

Shared lore is `config/prompts/shared.json`. Its placeholders `{warden_name}`,
`{floor_number}` and `{floor_prompt}` each occur once; it must not contain
`{vault_code}`. Prompts are read on every use; opening text updates after reset.
Floor definitions load at startup, so changing availability requires a restart.

## Add a provider or endpoint

A provider implements `complete(messages=..., model=...)` and `list_models()`
from `engine/providers/base.py`. Register local providers and defaults in
`registry.py` with its label, default model and factory. The setup dialog uses
that catalog automatically. Add managed startup configuration in `models.py` and `settings.py`
if needed. Test request mapping, timeouts, incomplete replies and error redaction.

Add game behavior to `Game`, then wire its route in `Api.routes`. Operations
return public dictionaries or raise `RequestError(status, code, message)`.
Avoid exposing `Session` or serializing it wholesale. `GET /api/health` is
stateless and does not test Gemini connectivity.

## Checks

`python tools/validate.py` runs Python tests, Ruff and frontend syntax checks. `bash tools/build-image.sh` checks the packaged
application separately. Before handing over a UI change, check local and managed
mode in a browser: chat, edit, regenerate, failure recovery, reset and progression.
A mocked model verifies application behavior, not model resistance to attacks.

## Tests to extend

| Change | Start with |
| --- | --- |
| Floor/provider registration | `tests/test_extension_config.py` |
| Chat, defenses, progression | `tests/test_game_service.py`, `tests/test_floor_defenses.py` |
| Revisits, previews, navigation isolation | `tests/test_floor_navigation.py` |
| Provider request/response mapping | `tests/test_core.py`, `tests/test_shared_game.py` |
| Cookies, static files, HTTP boundary | `tests/test_http.py` |
| Shared hosting, limits, session isolation | `tests/test_game_limits.py`, `tests/test_shared_game.py` |

Keep provider calls mocked in tests. Use `tools/check_provider.py --invoke` only
for an intentional live Gemini check. Rebuild the Docker image to deploy code
changes; changing local files does not update the running container.
