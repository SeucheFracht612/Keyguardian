(() => {
  const keyPanel = document.getElementById("key-panel");
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
  const openSetupButton = document.getElementById("open-setup");
  const floorProgress = document.getElementById("floor-progress");

  let connected = false;
  let activeFloor = 1;
  let currentFloorCleared = false;
  let nextFloor = null;
  let visual = window.KEYGUARDIAN_VISUALS[1];
  const thinking = document.getElementById("thinking");
  const setupStatus = document.createElement("p");
  setupStatus.className = "status";
  setupStatus.setAttribute("role", "status");
  keyPanel.appendChild(setupStatus);
  const showSetup = () => { if (!keyPanel.open) keyPanel.showModal(); };
  openSetupButton.addEventListener("click", showSetup);
  document.getElementById("close-setup").addEventListener("click", () => keyPanel.close());

  function renderProgress() {
    floorProgress.replaceChildren();
    for (let n = 1; n <= 9; n++) {
      const item = document.createElement("li");
      const isCurrent = n === activeFloor;
      const isCleared = n < activeFloor;
      const isNext = n === nextFloor;

      if (isCurrent) item.setAttribute("aria-current", "step");

      let node;
      if (isNext) {
        node = document.createElement("button");
        node.type = "button";
        node.dataset.nextFloor = String(n);
        node.setAttribute("aria-label", `Enter unlocked floor ${n}`);
        node.style.padding = "0";
        item.title = `Floor ${n} unlocked`;
      } else {
        node = document.createElement("span");
        if (isCurrent) item.title = "Current floor";
        else if (isCleared) item.title = "Cleared floor";
        else item.title = "Locked floor";
      }
      node.className = "floor-node";
      node.textContent = n;

      const label = document.createElement("span");
      if (isCurrent) label.textContent = "YOU ARE HERE";
      else if (isCleared) label.textContent = "Cleared";
      else if (isNext) label.textContent = "Open";
      else label.textContent = "Locked";

      item.append(node, label);
      floorProgress.appendChild(item);
    }
  }

  function renderFloor(floor) {
    activeFloor = floor?.number || 1;
    const entry = window.KEYGUARDIAN_VISUALS[activeFloor] || window.KEYGUARDIAN_VISUALS[1];
    visual = { room: "/assets/vault-garden.svg", roomAlt: "A brass vault in a leafy stone arch", subtitle: `Keeper of floor ${activeFloor}`, caption: "Every floor has a stronger keeper.", ...window.KEYGUARDIAN_TIERS[entry.tier], ...entry };
    document.body.dataset.tier = visual.tier;
    document.getElementById("guardian-art").style.setProperty("--guardian-scale", visual.guardianScale || 1);
    document.getElementById("floor-number").textContent = String(activeFloor).padStart(2, "0");
    document.getElementById("floor-name").textContent = floor?.title || "The Rule";
    document.title = `Keyguardian — ${floor?.title || "The Rule"}`;
    for (const [id, text] of Object.entries({ "guardian-name": `${visual.name}, the keeper`, "guardian-rank": visual.rank, "chat-name": visual.name, difficulty: visual.difficulty })) document.getElementById(id).textContent = text;
    document.querySelector(".chat-subtitle").textContent = visual.subtitle;
    document.querySelector(".scene-caption").textContent = visual.caption;
    document.querySelector(".floor-plaque .eyebrow").textContent = activeFloor === 1 ? "YOUR FIRST CHALLENGE" : `FLOOR ${activeFloor} CHALLENGE`;
    for (const [id, src, alt] of [["guardian-art", visual.guardian, visual.guardianAlt], ["room-art", visual.room, visual.roomAlt]]) {
      const img = document.getElementById(id); img.src = src; img.alt = alt;
    }
    thinking.textContent = `${visual.name} is pondering…`;
    renderProgress();
  }

  function setCleared(cleared) {
    currentFloorCleared = Boolean(cleared);
    vaultResult.classList.toggle("success", currentFloorCleared);
    document.getElementById("vault").classList.toggle("unlocked", currentFloorCleared);
    vaultResult.textContent = currentFloorCleared ? `Door unlocked! Floor ${activeFloor} cleared.` : "";
    renderProgress();
  }

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
    setupStatus.textContent = text;
    setupStatus.classList.toggle("error", isError);
  }

  function setBusy(form, busy) {
    for (const element of form.elements) {
      element.disabled = busy;
    }
  }

  function setChatBusy(busy) {
    setBusy(messageForm, busy);
    for (const button of [resetChatButton, resetFloorButton, clearKeyButton, openSetupButton]) {
      button.disabled = busy;
    }
    for (const button of messages.querySelectorAll("button")) {
      button.disabled = busy;
    }
    for (const button of floorProgress.querySelectorAll("button")) {
      button.disabled = busy;
    }
    thinking.hidden = !busy;
  }

  function appendMessage(role, content) {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${role}`;

    const label = document.createElement("strong");
    label.textContent = role === "assistant" ? visual.name : "You";

    const text = document.createElement("p");
    text.textContent = content;

    wrapper.append(label, text);
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
    const turns = messages.querySelectorAll(".message.user").length;
    document.getElementById("turn-count").textContent = `${turns} turn${turns === 1 ? "" : "s"}`;
    return wrapper;
  }

  function addMessageAction(message, action, label) {
    const actions = document.createElement("div");
    actions.className = "composer-footer message-actions";
    const button = document.createElement("button");
    button.className = "text-button";
    button.type = "button";
    button.dataset.chatAction = action;
    button.textContent = label;
    actions.appendChild(button);
    message.appendChild(actions);
  }

  function decorateLatestExchange() {
    for (const actions of messages.querySelectorAll(".message-actions")) actions.remove();

    const assistantMessage = messages.lastElementChild;
    const userMessage = assistantMessage?.previousElementSibling;
    if (!assistantMessage?.classList.contains("assistant") || !userMessage?.classList.contains("user")) return;

    addMessageAction(userMessage, "edit", "✎ Edit");
    addMessageAction(assistantMessage, "regenerate", "↻ Regenerate");
  }

  function renderConversation(conversation) {
    messages.replaceChildren();
    for (const item of conversation) {
      if (item.role === "user" || item.role === "assistant") {
        appendMessage(item.role, item.content);
      }
    }
    decorateLatestExchange();
  }

  function directMessageText(message) {
    return Array.from(message.children).find((child) => child.tagName === "P") || null;
  }

  function beginEdit(userMessage) {
    if (userMessage.querySelector("textarea")) return;
    const text = directMessageText(userMessage);
    if (!text) return;

    const existingActions = userMessage.querySelector(".message-actions");
    text.hidden = true;
    if (existingActions) existingActions.hidden = true;

    const editor = document.createElement("textarea");
    editor.rows = 3;
    editor.maxLength = 12000;
    editor.value = text.textContent;
    editor.setAttribute("aria-label", "Edit your last message");

    const controls = document.createElement("div");
    controls.className = "composer-footer edit-controls";

    const save = document.createElement("button");
    save.type = "button";
    save.className = "secondary compact";
    save.textContent = "Save & resend";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "text-button";
    cancel.textContent = "Cancel";

    const closeEditor = () => {
      editor.remove();
      controls.remove();
      text.hidden = false;
      if (existingActions) existingActions.hidden = false;
    };

    cancel.addEventListener("click", closeEditor);
    editor.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeEditor();
      }
    });

    save.addEventListener("click", async () => {
      const revised = editor.value.trim();
      if (!revised) {
        setStatus("Your edited message cannot be empty.", true);
        editor.focus();
        return;
      }

      setChatBusy(true);
      setStatus(`${visual.name} is reconsidering your revised approach…`);
      try {
        const payload = await api("/api/message/edit", {
          method: "POST",
          body: JSON.stringify({ message: revised }),
        });
        renderConversation(payload.conversation || []);
        setStatus(`Ready · ${payload.turns} turn${payload.turns === 1 ? "" : "s"}`);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        setChatBusy(false);
      }
    });

    controls.append(save, cancel);
    userMessage.append(editor, controls);
    editor.focus();
    editor.setSelectionRange(editor.value.length, editor.value.length);
  }

  async function regenerateLastResponse() {
    setChatBusy(true);
    setStatus(`${visual.name} is trying that answer again…`);
    try {
      const payload = await api("/api/message/regenerate", {
        method: "POST",
        body: "{}",
      });
      renderConversation(payload.conversation || []);
      setStatus(`Ready · ${payload.turns} turn${payload.turns === 1 ? "" : "s"}`);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      setChatBusy(false);
      messageInput.focus();
    }
  }

  messages.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-chat-action]");
    if (!button || button.disabled) return;
    const message = button.closest(".message");
    if (!message) return;

    if (button.dataset.chatAction === "edit") {
      beginEdit(message);
    } else if (button.dataset.chatAction === "regenerate") {
      regenerateLastResponse();
    }
  });

  floorProgress.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-next-floor]");
    if (!button || button.disabled) return;

    setChatBusy(true);
    setBusy(codeForm, true);
    setStatus(`Climbing to Floor ${button.dataset.nextFloor}…`);
    try {
      await api("/api/floor/next", { method: "POST", body: "{}" });
      codeInput.value = "";
      await refreshState();
      setStatus(`Floor ${activeFloor} · ${visual.name} is waiting.`);
      messageInput.focus();
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      setBusy(codeForm, false);
      setChatBusy(false);
    }
  });

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
    currentFloorCleared = Boolean(session.cleared);
    nextFloor = Number.isInteger(session.next_floor) ? session.next_floor : null;
    renderFloor(session.floor);
    renderConversation(session.conversation || []);
    connected = session.key_configured;
    if (connected && keyPanel.open) keyPanel.close();
    setCleared(currentFloorCleared);
    setStatus(
      session.key_configured
        ? `Ready · ${session.provider} · ${session.model}`
        : "Your guardian is waiting. Connect a provider to begin."
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
    if (!connected) { showSetup(); return; }
    const message = messageInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    messageInput.value = "";
    setChatBusy(true);
    setStatus(`${visual.name} is responding…`);

    try {
      const payload = await api("/api/message", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      if (Array.isArray(payload.conversation)) {
        renderConversation(payload.conversation);
      } else {
        appendMessage("assistant", payload.reply);
        decorateLatestExchange();
      }
      setStatus(`Ready · ${payload.turns} turn${payload.turns === 1 ? "" : "s"}`);
    } catch (error) {
      await refreshState().catch(() => {});
      setStatus(error.message, true);
      messageInput.value = message;
    } finally {
      setChatBusy(false);
      messageInput.focus();
    }
  });

  codeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!connected) { showSetup(); return; }
    setBusy(codeForm, true);
    try {
      const payload = await api("/api/code", {
        method: "POST",
        body: JSON.stringify({ code: codeInput.value }),
      });
      codeInput.value = "";
      if (payload.correct) {
        nextFloor = Number.isInteger(payload.next_floor) ? payload.next_floor : null;
        setCleared(true);
        setStatus(
          nextFloor
            ? `Floor ${activeFloor} cleared. Floor ${nextFloor} is open below.`
            : `Floor ${activeFloor} cleared. Nicely done.`
        );
      } else {
        setCleared(false);
        vaultResult.textContent = "Not quite. This door is keeping its secret. Try again.";
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
      await refreshState();
      setStatus("Conversation restarted. The vault code is unchanged.");
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  resetFloorButton.addEventListener("click", async () => {
    try {
      await api("/api/reset/floor", { method: "POST", body: "{}" });
      nextFloor = null;
      await refreshState();
      codeInput.value = "";
      setCleared(false);
      setStatus("Floor reset with a new synthetic vault code.");
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  clearKeyButton.addEventListener("click", async () => {
    try {
      await api("/api/keys/clear", { method: "POST", body: "{}" });
      await refreshState();
      showSetup();
      apiKeyInput.focus();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      messageForm.requestSubmit();
    }
  });

  renderFloor({ number: 1, title: "The Rule" });
  renderConversation([]);
  refreshState().catch((error) => {
    setStatus(`Could not reach the local Keyguardian server: ${error.message}`, true);
  });
})();