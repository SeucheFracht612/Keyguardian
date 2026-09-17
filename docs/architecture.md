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
- Provider credentials live outside game state. Never log keys, prompts,
  conversations, cookies or model response bodies.
- One process/worker and one application instance while state is in RAM. The session store
  removes local provider keys on expiry. Resets do not reset request allowances.
- Anonymous limits apply to session and network, not verified people. Cookie
  copying shares a game. Network hashes and limits reset on server restart.
- Trust forwarded IPs only from explicitly configured proxy networks. The proxy
  must append the client IP without a port; prevent direct access around it.

## Add or change a floor

1. Edit `config/floors.json`: contiguous numbers, cumulative protection names.
   Use unique slugs and JSON booleans for `implemented`. Playable floors must
   precede planned floors; progression cannot jump over an unavailable floor.
2. Add `config/prompts/floor-NN.json` with `warden_name`, `system_prompt` and
   `opening_message`. The floor prompt contains `{vault_code}` exactly once.
3. Add runtime defenses under `engine/middleware/` and register their factories
   in `engine/pipeline.py`. A defense implements `before(context)` and
   `after(context)`, mutating model messages/reply or raising a safe `RequestError`.
   Both stages run in the floor's declared order; each request gets fresh instances.
4. Add presentation overrides in `web/floor-visuals.js`, then set `implemented`
   to true. Test inherited behavior, blocked input/output, retries and progression.

Floors 1–2 use prompt-only defenses. Unknown protection names on an implemented
floor fail startup. Input defenses see the full model conversation; they should
process untrusted history as needed. Stored conversation keeps the player's
original input. Output defenses run before a reply is saved or returned.

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
| Chat, defenses, progression | `tests/test_game_service.py` |
| Provider request/response mapping | `tests/test_core.py`, `tests/test_shared_game.py` |
| Cookies, static files, HTTP boundary | `tests/test_http.py` |
| Shared hosting, limits, session isolation | `tests/test_game_limits.py`, `tests/test_shared_game.py` |

Keep provider calls mocked in tests. Use `tools/check_provider.py --invoke` only
for an intentional live Gemini check. Rebuild the Docker image to deploy code
changes; changing local files does not update the running container.
