# Keyguardian

Prompt-injection training game. Players try to make an AI guardian reveal a
synthetic vault code. Floors 1–5 are playable; floors 6–9 have explorable previews.
Use the floor strip to visit any room. Each room keeps its code, conversation and
clear status for the life of your session.

## Run locally

Python 3.13+. No packages or frontend build required:

```bash
python app.py
```

Open <http://127.0.0.1:8765>. Choose a provider and enter its API key in the setup
dialog. Gemini defaults to `gemini-3.1-flash-lite`; DeepSeek and OpenAI are also
supported. Keys and games stay in server memory. `KEYGUARDIAN_NO_BROWSER=1`
disables automatic browser opening.

For the shared Gemini configuration, set `KEYGUARDIAN_LLM_BACKEND=gemini` and
supply `GEMINI_API_KEY` through your shell or secret manager before starting.
This hides the provider dialog. Leave deployment mode at `local` for local HTTP.
The app does not load `.env` files automatically.

## Develop

```bash
python -m venv .venv
# Activate .venv using your shell's activation command.
python -m pip install -r requirements-dev.txt
python tools/validate.py
```

The full check needs Node 20+ for JavaScript syntax checks. Node is not needed to
run the game. Tests use simulated providers and make no paid model calls.

Python-only tests:

```bash
python -m unittest discover -s tests
```

CI runs the full check and builds/smoke-tests the Docker image.

## Project guide

- [Intended floor progression](docs/progression.md)
- [Architecture and extension points](docs/architecture.md)
- [Server configuration](docs/configuration.md)
- [Development tools](tools/README.md)

The game needs no login or database. Each browser has its own game cookie;
copying that cookie shares the game. Games and API keys are kept in memory and
are lost when the server restarts. Run one application process while using this
in-memory storage.
