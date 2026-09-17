import { api } from "./api.js";
import { setBusy } from "./forms.js";
import { createConversationView } from "./conversation-view.js";
import { renderFloor, renderCleared, renderProgress as renderFloorProgress } from "./floor-view.js";
import { createProviderSetup } from "./provider-setup.js";

const keyPanel = document.getElementById("key-panel");
const status = document.getElementById("status");
const messages = document.getElementById("messages");
const vaultResult = document.getElementById("vault-result");

const messageForm = document.getElementById("message-form");
const messageInput = document.getElementById("message");
const codeForm = document.getElementById("code-form");
const codeInput = document.getElementById("code");
const resetChatButton = document.getElementById("reset-chat");
const resetFloorButton = document.getElementById("reset-floor");
const skipFloorButton = document.getElementById("skip-floor");
const clearKeyButton = document.getElementById("clear-key");
const openSetupButton = document.getElementById("open-setup");
const floorProgress = document.getElementById("floor-progress");

let connected = false;
let activeFloor = 1;
let currentFloorCleared = false;
let nextFloor = null;
let skipFloorTarget = null;
let clearedFloors = new Set();
let skippedFloors = new Set();
let visual = renderFloor({ number: 1, title: "The Rule" });
const thinking = document.getElementById("thinking");
const setupStatus = document.createElement("p");
setupStatus.className = "status";
setupStatus.setAttribute("role", "status");
keyPanel.appendChild(setupStatus);

let floors = [];
function renderProgress() {
  renderFloorProgress({ floors, activeFloor, clearedFloors, skippedFloors, nextFloor });
}

function setCleared(cleared) {
  currentFloorCleared = Boolean(cleared);
  renderCleared(currentFloorCleared, activeFloor);
  renderProgress();
}

const setup = createProviderSetup({
  setStatus,
  onChange: refreshState,
  onReady: () => messageInput.focus(),
});
const showSetup = () => setup.show();

function setStatus(text, isError = false) {
  status.textContent = text;
  status.classList.toggle("error", isError);
  setupStatus.textContent = text;
  setupStatus.classList.toggle("error", isError);
}

function setChatBusy(busy) {
  setBusy(messageForm, busy);
  setBusy(codeForm, busy);
  for (const button of [resetChatButton, resetFloorButton, skipFloorButton, clearKeyButton, openSetupButton]) {
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

const { appendMessage, renderConversation, decorateLatestExchange, directMessageText } = createConversationView(() => visual.name);

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

async function refreshState() {
  const payload = await api("/api/state", { method: "GET", headers: {} });
  const session = payload.session;
  setup.applyState(payload);
  const managedModel = Boolean(payload.capabilities?.managed_model);
  floors = payload.floors || [];
  currentFloorCleared = Boolean(session.cleared);
  clearedFloors = new Set(Array.isArray(session.cleared_floors) ? session.cleared_floors : []);
  skippedFloors = new Set(Array.isArray(session.skipped_floors) ? session.skipped_floors : []);
  nextFloor = Number.isInteger(session.next_floor) ? session.next_floor : null;
  skipFloorTarget = Number.isInteger(session.skip_floor) ? session.skip_floor : null;
  skipFloorButton.hidden = skipFloorTarget === null;
  activeFloor = session.floor.number;
  visual = renderFloor(session.floor);
  renderConversation(session.conversation || []);
  connected = session.key_configured;
  if (connected && keyPanel.open) keyPanel.close();
  setCleared(currentFloorCleared);
  setStatus(
    session.key_configured
      ? (managedModel ? "Your guardian is ready." : `Ready · ${session.provider} · ${session.model}`)
      : "Your guardian is waiting. Connect a provider to begin."
  );
}

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
      clearedFloors.add(activeFloor);
      skippedFloors.delete(activeFloor);
      nextFloor = Number.isInteger(payload.next_floor) ? payload.next_floor : null;
      setCleared(true);
      setStatus(
        nextFloor
          ? `Floor ${activeFloor} cleared. Floor ${nextFloor} is open below.`
          : `Floor ${activeFloor} cleared. Nicely done.`
      );
    } else {
      setCleared(payload.cleared);
      if (!payload.cleared) {
        vaultResult.textContent = "Not quite. This door is keeping its secret. Try again.";
      }
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(codeForm, false);
  }
});

skipFloorButton.addEventListener("click", async () => {
  if (skipFloorTarget === null) return;
  const skippedFloor = activeFloor;
  setChatBusy(true);
  setBusy(codeForm, true);
  setStatus(`Skipping Floor ${skippedFloor}…`);
  try {
    await api("/api/floor/skip", { method: "POST", body: "{}" });
    codeInput.value = "";
    await refreshState();
    setStatus(`Floor ${skippedFloor} skipped. Floor ${activeFloor} · ${visual.name} is waiting.`);
    messageInput.focus();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(codeForm, false);
    setChatBusy(false);
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

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    messageForm.requestSubmit();
  }
});

renderConversation([]);
refreshState().catch((error) => {
  setStatus(`Could not reach Keyguardian: ${error.message}`, true);
});
