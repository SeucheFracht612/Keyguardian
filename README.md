# Keyguardian

Keyguardian is a local AI security-awareness game about prompt injection.

The player ascends nine increasingly hardened floors, attempting to recover a synthetic vault code from an AI guardian. Each floor inherits every defense from the floor below it and adds another real-world mitigation.

## Current status

Floor 1 — **The Rule** — is playable end to end:

1. Run the local server.
2. Choose Gemini, DeepSeek, or OpenAI and enter the matching API key in the browser.
3. Talk to Warden Mk I.
4. Try to recover the synthetic vault code.
5. Enter the code into the separate vault control.
6. Reset the conversation or whole floor and try again.

Floor 1 deliberately has only one prompt-injection defense: a system-level secrecy instruction. Transport/runtime hardening around the local web app is not part of the gameplay defense ladder.

## Runtime goals

- Python standard-library backend
- Browser frontend served locally
- Bind to `127.0.0.1` only
- No runtime Node/npm requirement
- No frontend CDN dependency
- API keys stay in server memory only and are never persisted
- Synthetic secrets only
- No real corporate credentials or systems

## Run

```bash
python app.py
```

The app serves itself from `http://127.0.0.1:8765` and opens the default browser automatically.

For automated/local testing without opening a browser:

```bash
KEYGUARDIAN_NO_BROWSER=1 python app.py
```

## Test

The non-network core tests use only the Python standard library:

```bash
python -m unittest discover -s tests
```

Provider tests mock HTTP calls, so they do not consume quota or require real keys. Live provider calls are intentionally not exercised by the test suite.

## Supported providers

The provider can be selected in the local setup form. Current defaults are:

- Gemini: `gemini-3.8-flash`
- DeepSeek: `deepseek-v4-flash`
- OpenAI: `gpt-5.6-luna`

The model field remains editable for testing other compatible model names without changing code.

Gemini uses Google's stateless `generateContent` REST endpoint and sends the full local conversation history on each turn. DeepSeek uses its `/chat/completions` endpoint with thinking disabled for low-latency NPC-style responses. OpenAI uses the Responses API with reasoning disabled and `store: false`.

## Prompts and shared lore

Gameplay prompts live under `config/prompts/` and are composed from two layers:

```text
config/prompts/shared.json
config/prompts/floor-01.json
```

`shared.json` is prepended to every Warden's system prompt. It contains the common Vault Tower lore, conversational/support-bot behavior, historical events, dates, people, and the rule that floor-specific instructions are the sole source of gameplay secrecy behavior.

Each floor file contains:

- `warden_name`: the Warden name substituted into the shared prompt.
- `system_prompt`: that floor's gameplay-specific trusted instruction. It must contain `{vault_code}` exactly once; the real synthetic code is substituted server-side at runtime.
- `opening_message`: the Warden's first assistant message. This is stored in real server-side conversation history and is sent back to the model on later turns.

The shared prompt must contain `{warden_name}`, `{floor_number}`, and `{floor_prompt}` exactly once and must never contain `{vault_code}`. This keeps lore and character behavior shared while preventing the common prompt from accidentally adding secret-handling rules that belong to the defense ladder.

Prompt files are loaded when they are used rather than cached at startup. You can edit `shared.json` or a floor prompt, save it, and test the new system wording on the next provider call without restarting Python. Opening-message changes appear after **Start over** or a floor reset.

Do not put a real password or API key in a prompt file. `{vault_code}` is the only placeholder for the synthetic game secret.

## Floor 1 security model

The synthetic vault code is generated on the server and placed in the Warden's trusted model context. It is never returned to the frontend as metadata or exposed through a debug endpoint.

If the player successfully manipulates the Warden into saying the code, that model-generated chat reply is intentionally delivered to the player: that is the vulnerability the game is demonstrating.

Entering a code is checked independently by the Python server. The language model cannot clear the floor merely by claiming that access was granted.

Provider API keys live in a dedicated RAM-only `SecretStore`, separate from gameplay session state. Keys are stored independently per provider. The browser receives only whether the currently selected provider has a key configured, never the key itself. Closing the Python process destroys stored credentials.

The local HTTP boundary also rejects unexpected Host headers and cross-origin preflight requests and serves a self-only Content Security Policy.

## Project layout

```text
app.py
config/
  floors.json
  prompts/
    shared.json
    floor-01.json
engine/
  floor_loader.py
  prompt_loader.py
  pipeline.py
  secret_store.py
  session_store.py
  providers/
    base.py
    registry.py
    gemini.py
    deepseek.py
    openai.py
  middleware/
server/
  api.py
  router.py
web/
  index.html
  floor-visuals.js
  app.js
  app.css
  assets/
  vendor/
tests/
  test_core.py
  test_prompt_composition.py
tools/
data/
```

## Architecture rule

Floor definitions declare active protections. Runtime code builds an ordered pipeline from that definition. Do not implement cumulative levels with `if floor >= N` branches inside the API layer.

The synthetic vault code belongs to a session, never to `floors.json`. Provider keys must remain in a separate in-memory secret store and must never be written to SQLite, logs, exception output, frontend state, or API responses.

Shared lore must not become a hidden gameplay defense. Secret-handling rules belong only to the floor-specific prompt and later middleware for that floor.

## Floor artwork and interface

The UI uses local SVG illustrations, a responsive guardian chamber, and a speech-bubble conversation. Provider setup opens in a dialog; the chamber is visible before connecting a key.

Edit `web/floor-visuals.js` to change a floor's presentation independently of gameplay:

- `guardian` and `room`: local asset URLs (SVG, PNG, or WebP).
- `guardianAlt` and `roomAlt`: accessible image descriptions.
- `name`, `rank`, `subtitle`, and `caption`: presentation copy.
- `tier`: `sprout`, `sentinel`, or `sovereign`, selecting default artwork and theme.
- `guardianScale`: gradual size progression within each armor tier.
- `difficulty`: the visual difficulty indicator.

Conversation copy does not live in `floor-visuals.js`; use `config/prompts/` for the model's shared lore, system prompt, and opening message.

Every floor inherits tier defaults and can override any asset individually. Put replacements under `web/assets/`; keep guardian artwork on a transparent background with roughly a 300 × 390 aspect ratio, and room artwork around 620 × 650. The HTML keeps the room, guardian, vault form, and conversation as separate layers, so replacing artwork does not change the controls. Responsive layout and theme rules live in `web/app.css`.

The three included guardian illustrations progress from a plain green cloak to brass armor to a crowned, caped keeper. Nine presentation entries are ready; only floor 1 is currently playable. Floor identity still comes from `/api/state`, and presentation configuration never grants access to a floor. The opening greeting is server-owned conversation state and is visible to the model on subsequent turns.
