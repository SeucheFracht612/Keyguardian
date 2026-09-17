# Configuration

`python app.py` runs locally on `127.0.0.1:8765`. Players choose a provider and
supply their own key. The application reads environment variables at startup;
it does not load `.env` files.

## Server-owned Gemini key

Set `KEYGUARDIAN_LLM_BACKEND=gemini` and `GEMINI_API_KEY`. The provider dialog is
then hidden. `KEYGUARDIAN_GEMINI_MODEL` optionally overrides the registered
default. Keep the key in your environment or secret manager, outside Git.

## Shared server

Use a WSGI server and HTTPS reverse proxy. Install `requirements-server.txt`, then
run `gunicorn --config gunicorn.conf.py 'server.wsgi:create_app()'`.

| Variable | Shared-server value |
| --- | --- |
| `KEYGUARDIAN_DEPLOYMENT` | `shared` |
| `KEYGUARDIAN_LLM_BACKEND` | `gemini` |
| `GEMINI_API_KEY` | Server-owned key |
| `KEYGUARDIAN_SECURE_COOKIES` | `1` |
| `KEYGUARDIAN_ALLOWED_HOSTS` | Explicit comma-separated hostnames, without scheme or port |
| `KEYGUARDIAN_TRUSTED_PROXY_CIDRS` | Explicit proxy networks, if using forwarded client IPs |
| `PORT` | Container/server port; default `8080` |

The proxy must append the bare client IP to `X-Forwarded-For`. Only configured
proxy peers are trusted. Restrict direct access to the application behind the
proxy. With no trusted proxy configured, quotas use the direct connection IP.

Use exactly one process and one application instance. Sessions and request
allowances are process-local; multiple replicas would split player state.
`GET /api/health` tests the HTTP service, not model connectivity.

## Limits

`engine/settings.py` defines defaults and valid ranges. Each field maps to
`KEYGUARDIAN_<UPPERCASE_FIELD_NAME>`; booleans use `0` or `1`. Shared mode enforces
per-session and per-network request limits. Model calls with a server-owned key
also have concurrency and daily allowances. Failed model calls consume allowance;
resetting a game does not replenish it.

## Docker

`docker build -t keyguardian:game .` builds the game image. For a local test:

```bash
docker run --rm -p 127.0.0.1:8080:8080 keyguardian:game
```

Open <http://127.0.0.1:8080>. The image defaults to local mode. To run a shared
server, supply the settings above and terminate HTTPS at your reverse proxy.
`bash tools/build-image.sh` additionally runs tests and exports a local archive.
