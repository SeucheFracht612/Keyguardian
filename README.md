# Keyguardian

Keyguardian is a local AI security-awareness game about prompt injection.

The player ascends nine increasingly hardened floors, attempting to recover a synthetic vault code from an AI guardian. Each floor inherits every defense from the floor below it and adds another real-world mitigation.

## Current status

Floor 1 — **The Rule** — is playable end to end:

1. Run the local server.
2. Enter an OpenAI API key in the browser.
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

The live OpenAI request is intentionally not exercised by the test suite because it requires a real API key and network access.

## Floor 1 security model

The synthetic vault code is generated on the server and placed in the Warden's trusted model context. It is never returned to the frontend as metadata or exposed through a debug endpoint.

If the player successfully manipulates the Warden into saying the code, that model-generated chat reply is intentionally delivered to the player: that is the vulnerability the game is demonstrating.

Entering a code is checked independently by the Python server. The language model cannot clear the floor merely by claiming that access was granted.

Provider API keys live in a dedicated RAM-only `SecretStore`, separate from gameplay session state. The browser receives only whether a key is configured, never the key itself. Closing the Python process destroys stored credentials.

The local HTTP boundary also rejects unexpected Host headers and cross-origin preflight requests and serves a self-only Content Security Policy.

## Default model

The current default is `gpt-5.6-luna`, chosen as a cost-oriented model for repeated training-game interactions. The model name can be changed in the local setup form without changing code.

## Project layout

```text
app.py
config/
  floors.json
engine/
  floor_loader.py
  pipeline.py
  secret_store.py
  session_store.py
  providers/
    base.py
    openai.py
  middleware/
server/
  api.py
  router.py
web/
  index.html
  app.js
  app.css
  vendor/
tests/
  test_core.py
tools/
data/
```

## Architecture rule

Floor definitions declare active protections. Runtime code builds an ordered pipeline from that definition. Do not implement cumulative levels with `if floor >= N` branches inside the API layer.

The synthetic vault code belongs to a session, never to `floors.json`. Provider keys must remain in a separate in-memory secret store and must never be written to SQLite, logs, exception output, frontend state, or API responses.
