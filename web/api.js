export async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  }).catch(() => {
    throw new Error("Connection lost. Reload the page and try again.");
  });

  if (response.status === 401 || response.redirected) {
    throw new Error("Your sign-in has expired. Reload this page to sign in again.");
  }
  let payload = {};
  try {
    payload = await response.json();
  } catch (_) {
    throw new Error(`The server returned HTTP ${response.status}.`);
  }

  if (!response.ok) {
    const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
    error.code = payload.error;
    error.defense = payload.defense;
    throw error;
  }
  return payload;
}
