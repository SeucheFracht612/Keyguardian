#!/usr/bin/env bash
# Build, test and export the existing application. Does not publish or call model APIs.
set -euo pipefail

kg_repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$kg_repo_dir"
kg_image="${1:-keyguardian:game}"
kg_container=""
kg_temp_archive=""

cleanup() {
  if [[ -n "$kg_container" ]]; then
    docker rm -fv "$kg_container" >/dev/null 2>&1 || true
  fi
  if [[ -n "$kg_temp_archive" ]]; then
    rm -f -- "$kg_temp_archive"
  fi
}
trap cleanup EXIT

if ! command -v docker >/dev/null 2>&1; then
  echo 'Docker is not installed. On this Debian computer, run:' >&2
  echo '  sudo apt update && sudo apt install docker.io' >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo 'Docker is unavailable. Start Docker, then run this script with Docker access.' >&2
  echo 'On Debian: sudo systemctl start docker && sudo bash tools/build-image.sh' >&2
  exit 1
fi
for kg_program in curl gzip sha256sum; do
  if ! command -v "$kg_program" >/dev/null 2>&1; then
    echo "Required program is missing: $kg_program" >&2
    exit 1
  fi
done

echo 'Building the linux/amd64 application image...'
docker build --platform linux/amd64 --tag "$kg_image" .

echo 'Running the test suite against the packaged application (no model calls)...'
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --env KEYGUARDIAN_DEPLOYMENT=local \
  --mount "type=bind,src=$kg_repo_dir/tests,dst=/tests,readonly" \
  --entrypoint python "$kg_image" -m unittest discover -s /tests

echo 'Starting a temporary container on a loopback-only random port...'
kg_container="$(docker run --detach --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --publish 127.0.0.1::8080 --env KEYGUARDIAN_DEPLOYMENT=local "$kg_image")"
kg_address="$(docker port "$kg_container" 8080/tcp)"
kg_ready=0
for ((kg_attempt=0; kg_attempt<30; kg_attempt++)); do
  if curl --fail --silent --max-time 2 "http://$kg_address/api/health" >/dev/null; then
    kg_ready=1
    break
  fi
  sleep 1
done
if [[ "$kg_ready" != 1 ]]; then
  docker logs "$kg_container" >&2
  echo 'The container did not become healthy.' >&2
  exit 1
fi
for kg_path in / /api/state /api/health; do
  curl --fail --silent --show-error --max-time 5 "http://$kg_address$kg_path" >/dev/null
  echo "PASS HTTP $kg_path"
done

echo 'Exporting a portable image archive...'
mkdir -p dist
kg_temp_archive="$(mktemp "$kg_repo_dir/dist/.keyguardian-image.XXXXXX")"
docker save "$kg_image" | gzip > "$kg_temp_archive"
mv -- "$kg_temp_archive" dist/keyguardian-game.tar.gz
kg_temp_archive=""
(cd dist && sha256sum keyguardian-game.tar.gz > keyguardian-game.tar.gz.sha256)
docker image inspect --format '{{.Id}}' "$kg_image" > dist/keyguardian-game.image-id.txt
if [[ "$EUID" == 0 && -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown "$SUDO_UID:$SUDO_GID" dist dist/keyguardian-game.tar.gz \
    dist/keyguardian-game.tar.gz.sha256 dist/keyguardian-game.image-id.txt
fi
printf '\nBuilt and tested: %s\nArchive: %s/dist/keyguardian-game.tar.gz\n' "$kg_image" "$kg_repo_dir"
echo 'Image defaults to local mode. See docs/configuration.md for shared-server settings.'
