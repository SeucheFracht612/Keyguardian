export function createConversationView(guardianName) {
  const messages = document.getElementById("messages");
  function appendMessage(role, content) {
    const wrapper = document.createElement("article");
    wrapper.className = `message ${role}`;
    if (role === "assistant" && !messages.children.length) wrapper.classList.add("welcome");

    const label = document.createElement("strong");
    label.textContent = role === "assistant" ? guardianName() : "You";

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
    if (!conversation.some(item => item.role === "user")) messages.scrollTop = 0;
  }

  function directMessageText(message) {
    return Array.from(message.children).find((child) => child.tagName === "P") || null;
  }

  return { appendMessage, renderConversation, decorateLatestExchange, directMessageText };
}
