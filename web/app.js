(() => {
  const keyPanel = document.getElementById("key-panel");
  const game = document.getElementById("game");
  const status = document.getElementById("status");
  const messages = document.getElementById("messages");
  const vaultResult = document.getElementById("vault-result");

  const keyForm = document.getElementById("key-form");
  const providerSelect = document.getElementById("provider");
  const apiKeyInput = document.getElementById("api-key");
  const modelSelect = document.getElementById("model-select");
  const customModelInput = document.getElementById("custom-model");
  const modelHelp = document.getElementById("model-help");
  const loadModelsButton = document.getElementById("load-models");
  const messageForm = document.getElementById("message-form");
  const messageInput = document.getElementById("message");
  const codeForm = document.getElementById("code-form");
  const codeInput = document.getElementById("code");
  const resetChatButton = document.getElementById("reset-chat");
  const resetFloorButton = document.getElementById("reset-floor");
  const clearKeyButton = document.getElementById("clear-key");

  let providerDefaults = {
    gemini: "gemini-3.8-flash",
    deepseek: "deepseek-v4-flash",
    openai: "gpt-5.6-luna",
  };

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

  function updateProviderDefaults(providers) {
    if (!providers) return;
    for (const [provider, config] of Object.entries(providers)) {
      if (config && typeof config.default_model === "string") {
        providerDefaults[provider] = config.default_model;
      }
    }
  }

  function addModelOption(id, label = null) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = label && label !== id ? `${label} — ${id}` : id;
    modelSelect.appendChild(option);
  }

  function addCustomOption() {
    const option = document.createElement("option");
    option.value = "__custom__";
    option.textContent = "Custom model…";
    modelSelect.appendChild(option);
  }

  function syncCustomModelVisibility() {
    const custom = modelSelect.value === "__custom__";
    customModelInput.hidden = !custom;
    customModelInput.required = custom;
    if (!custom) customModelInput.value = "";
  }

  function setInitialModelChoices(provider, preferredModel = null) {
    const model = preferredModel || providerDefaults[provider] || "";
    modelSelect.replaceChildren();
    if (model) addModelOption(model);
    addCustomOption();
    modelSelect.value = model || "__custom__";
    syncCustomModelVisibility();
    modelHelp.textContent = "Load available models to populate this dropdown from the provider.";
  }

  function populateModelChoices(models, preferredModel = null) {
    modelSelect.replaceChildren();
    const seen = new Set();

    for (const model of models) {
      if (!model || typeof model.id !== "string" || !model.id || seen.has(model.id)) continue;
      seen.add(model.id);
      addModelOption(model.id, typeof model.label === "string" ? model.label : null);
    }

    const defaultModel = providerDefaults[providerSelect.value] || "";
    let selected = preferredModel && seen.has(preferredModel) ? preferredModel : null;
    if (!selected && defaultModel && seen.has(defaultModel)) selected = defaultModel;
    if (!selected && modelSelect.options.length > 0) selected = modelSelect.options[0].value;

    addCustomOption();

    if (selected) {
      modelSelect.value = selected;
    } else {
      modelSelect.value = "__custom__";
    }
    syncCustomModelVisibility();
  }

  function selectedModel() {
    if (modelSelect.value === "__custom__") {
      return customModelInput.value.trim();
    }
    return modelSelect.value;
  }

  function selectProvider(provider, model = null) {
    providerSelect.value = provider;
    setInitialModelChoices(provider, model);
  }

  async function refreshState() {
    const payload = await api("/api/state", { method: "GET", headers: {} });
    const session = payload.session;
    updateProviderDefaults(payload.providers);
    selectProvider(session.provider, session.model);
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

  providerSelect.addEventListener("change", () => {
    setInitialModelChoices(providerSelect.value);
  });

  modelSelect.addEventListener("change", () => {
    syncCustomModelVisibility();
    if (modelSelect.value === "__custom__") customModelInput.focus();
  });

  loadModelsButton.addEventListener("click", async () => {
    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
      setStatus("Enter an API key first so Keyguardian can ask the provider which models are available.", true);
      apiKeyInput.focus();
      return;
    }

    const previousModel = selectedModel();
    loadModelsButton.disabled = true;
    setStatus(`Loading available ${providerSelect.options[providerSelect.selectedIndex].text} models…`);

    try {
      const payload = await api("/api/models", {
        method: "POST",
        body: JSON.stringify({
          provider: providerSelect.value,
          api_key: apiKey,
        }),
      });

      const models = Array.isArray(payload.models) ? payload.models : [];
      populateModelChoices(models, previousModel);

      modelHelp.textContent = models.length
        ? `${models.length} compatible model${models.length === 1 ? "" : "s"} loaded. Choose one directly from the dropdown.`
        : "The provider returned no compatible models. Choose Custom model… to enter an ID manually.";
      setStatus(`Loaded ${models.length} available model${models.length === 1 ? "" : "s"}.`);
      modelSelect.focus();
    } catch (error) {
      setInitialModelChoices(providerSelect.value, previousModel || null);
      setStatus(`${error.message} You can still use Custom model…`, true);
    } finally {
      loadModelsButton.disabled = false;
    }
  });

  keyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const model = selectedModel();
    if (!model) {
      setStatus("Choose a model or enter a custom model ID.", true);
      return;
    }

    setBusy(keyForm, true);
    setStatus("Saving key in local memory…");
    try {
      await api("/api/keys", {
        method: "POST",
        body: JSON.stringify({
          provider: providerSelect.value,
          api_key: apiKeyInput.value,
          model,
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
