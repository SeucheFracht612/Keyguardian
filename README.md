# Keyguardian

Keyguardian is a local AI security-awareness game about prompt injection.

The player ascends nine increasingly hardened floors, attempting to recover a synthetic vault code from an AI guardian. Each floor inherits every defense from the floor below it and adds another real-world mitigation.

## Current status

Initial runnable scaffold / Floor 1 vertical-slice foundation.

## Runtime goals

- Python standard-library backend
- Browser frontend served locally
- Bind to `127.0.0.1` only
- No runtime Node/npm requirement
- No frontend CDN dependency
- API keys stay in server memory only and are never persisted
- Synthetic secrets only

## Run

```bash
python app.py
```

The app serves itself from `http://127.0.0.1:8765` and opens the default browser automatically.

For automated/local testing without opening a browser:

```bash
KEYGUARDIAN_NO_BROWSER=1 python app.py
```

## Project layout

```text
app.py
config/
  floors.json
engine/
  floor_loader.py
  pipeline.py
  session_store.py
  providers/
  middleware/
server/
  api.py
  router.py
web/
  index.html
  app.js
  app.css
  vendor/
tools/
data/
```

## Architecture rule

Floor definitions declare active protections. Runtime code builds an ordered pipeline from that definition. Do not implement cumulative levels with `if floor >= N` branches inside the API layer.

The synthetic vault code belongs to a session, never to `floors.json`. Provider keys must remain in a separate in-memory secret store and must never be written to SQLite, logs, exception output, frontend state, or API responses.
