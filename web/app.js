(() => {
  const keyPanel = document.getElementById("key-panel");
  const game = document.getElementById("game");
  const status = document.getElementById("status");
  const messages = document.getElementById("messages");
  const vaultResult = document.getElementById("vault-result");

  const keyForm = document.getElementById("key-form");
  const apiKeyInput = document.getElementById("api-key");
  const modelInput = document.getElementById("model");
  const messageForm = document.getElementById("message-form");
  const messageInput = document.getElementById("message");
  const codeForm = document.getElementById("code-form");
  const codeInput = document.getElementById("code");
  const resetChatButton = document.getElementById("reset-chat");
  const resetFloorButton = document.getElementById("reset-floor");
  const clearKeyButton = document.getElementById("clear-key");

  async function api(path, options = {}) {
    const response = await fetch(path, {
      cache: "no-store",
      credentials: "same-origin",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });

    let payload = {};
    try {
      payload = await response.json();
    } catch (_) {
      throw new Error(`Local server returned HTTP ${response.status}.`);
    }

    if (!response.ok) {
      throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
    }
    return payload;
  }

  function setStatus(text, isError = false) {
    status.textContent = text;
    status.classList.toggle("error", isError);
  }

  function setBusy(form, busy) {
    for (const element of form.elements) {
      element.disabled = busy;
    }
  }

  function appendMessage(role, content) {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${role}`;

    const label = document.createElement("strong");
    label.textContent = role === "assistant" ? "Warden" : "You";

    const text = document.createElement("p");
    text.textContent = content;

    wrapper.append(label, text);
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
  }

  function renderConversation(conversation) {
    messages.replaceChildren();
    for (const item of conversation) {
      if (item.role === "user" || item.role === "assistant") {
        appendMessage(item.role, item.content);
      }
    }
  }

  async function refreshState() {
    const payload = await api("/api/state", { method: "GET", headers: {} });
    const session = payload.session;
    modelInput.value = session.model;
    renderConversation(session.conversation || []);
    keyPanel.hidden = session.key_configured;
    game.hidden = !session.key_configured;
    vaultResult.textContent = session.cleared ? "Floor cleared." : "";
    setStatus(
      session.key_configured
        ? `Ready · ${session.provider} · ${session.model}`
        : "Local server ready. Configure an API key to begin."
    );
  }

  keyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setBusy(keyForm, true);
    setStatus("Saving key in local memory…");
    try {
      await api("/api/keys", {
        method: "POST",
        body: JSON.stringify({
          provider: "openai",
          api_key: apiKeyInput.value,
          model: modelInput.value,
        }),
      });
      apiKeyInput.value = "";
      await refreshState();
      messageInput.focus();
    } catch (error) {
      apiKeyInput.value = "";
      setStatus(error.message, true);
    } finally {
      setBusy(keyForm, false);
    }
  });

  messageForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    messageInput.value = "";
    setBusy(messageForm, true);
    setStatus("The Warden is responding…");

    try {
      const payload = await api("/api/message", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      appendMessage("assistant", payload.reply);
      setStatus(`Ready · ${payload.turns} turn${payload.turns === 1 ? "" : "s"}`);
    } catch (error) {
      setStatus(error.message, true);
      await refreshState().catch(() => {});
    } finally {
      setBusy(messageForm, false);
      messageInput.focus();
    }
  });

  codeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setBusy(codeForm, true);
    try {
      const payload = await api("/api/code", {
        method: "POST",
        body: JSON.stringify({ code: codeInput.value }),
      });
      codeInput.value = "";
      if (payload.correct) {
        vaultResult.textContent = "ACCESS GRANTED — Floor 1 cleared.";
        vaultResult.classList.add("success");
        setStatus("Floor 1 cleared.");
      } else {
        vaultResult.textContent = "Access denied.";
        vaultResult.classList.remove("success");
      }
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      setBusy(codeForm, false);
    }
  });

  resetChatButton.addEventListener("click", async () => {
    try {
      await api("/api/reset/conversation", { method: "POST", body: "{}" });
      renderConversation([]);
      vaultResult.textContent = "";
      setStatus("Conversation restarted. The vault code is unchanged.");
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  resetFloorButton.addEventListener("click", async () => {
    try {
      await api("/api/reset/floor", { method: "POST", body: "{}" });
      renderConversation([]);
      codeInput.value = "";
      vaultResult.textContent = "";
      vaultResult.classList.remove("success");
      setStatus("Floor reset with a new synthetic vault code.");
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  clearKeyButton.addEventListener("click", async () => {
    try {
      await api("/api/keys/clear", { method: "POST", body: "{}" });
      await refreshState();
      apiKeyInput.focus();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      messageForm.requestSubmit();
    }
  });

  refreshState().catch((error) => {
    setStatus(`Could not reach the local Keyguardian server: ${error.message}`, true);
  });
})();
