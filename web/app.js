(async function () {
  const status = document.getElementById("status");

  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    const payload = await response.json();
    status.textContent = payload.ok
      ? "Local server online. Floor engine ready for implementation."
      : "Server responded, but health check failed.";
  } catch (error) {
    status.textContent = "Could not reach the local Keyguardian server.";
    console.error(error);
  }
})();
