import { api } from "./api.js";
import { setBusy } from "./forms.js";

export function createProviderSetup({ setStatus, onChange, onReady }) {
  const keyPanel = document.getElementById("key-panel");
  const openSetupButton = document.getElementById("open-setup");
  const clearKeyButton = document.getElementById("clear-key");
  const keyForm = document.getElementById("key-form");
  const providerSelect = document.getElementById("provider");
  const apiKeyInput = document.getElementById("api-key");
  const modelSelect = document.getElementById("model-select");
  const customModelInput = document.getElementById("custom-model");
  const modelHelp = document.getElementById("model-help");
  const loadModelsButton = document.getElementById("load-models");
  const showSetup = () => { if (!keyPanel.open) keyPanel.showModal(); };
  openSetupButton.addEventListener("click", showSetup);
  document.getElementById("close-setup").addEventListener("click", () => keyPanel.close());
  let providerDefaults = {};

  function updateProviderDefaults(providers) {
    if (!providers) return;
    providerDefaults = {};
    providerSelect.replaceChildren();
    for (const [provider, config] of Object.entries(providers)) {
      if (config && typeof config.default_model === "string") {
        providerDefaults[provider] = config.default_model;
        const option = document.createElement("option");
        option.value = provider;
        option.textContent = config.label || provider;
        providerSelect.appendChild(option);
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
      await onChange();
      onReady();
    } catch (error) {
      apiKeyInput.value = "";
      setStatus(error.message, true);
    } finally {
      setBusy(keyForm, false);
    }
  });

  clearKeyButton.addEventListener("click", async () => {
    try {
      await api("/api/keys/clear", { method: "POST", body: "{}" });
      await onChange();
      showSetup();
      apiKeyInput.focus();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  return {
    show: showSetup,
    applyState(payload) {
      updateProviderDefaults(payload.providers);
      const managed = Boolean(payload.capabilities?.managed_model);
      openSetupButton.hidden = managed;
      clearKeyButton.hidden = managed;
      if (!managed) selectProvider(payload.session.provider, payload.session.model);
      if ((managed || payload.session.key_configured) && keyPanel.open) keyPanel.close();
    },
  };
}
