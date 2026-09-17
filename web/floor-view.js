import { FLOOR_VISUALS, TIERS } from "./floor-visuals.js";
import { renderWards } from "./wards.js";

export function renderProgress({ floors, activeFloor, clearedFloors, skippedFloors, visitedFloors }) {
  const floorProgress = document.getElementById("floor-progress");
  floorProgress.replaceChildren();
  for (const floor of floors) {
    const n = floor.number;
    const item = document.createElement("li");
    const current = n === activeFloor;
    const state = current ? "current" : clearedFloors.has(n) ? "cleared"
      : !floor.implemented ? "preview" : skippedFloors.has(n) ? "skipped"
      : visitedFloors.has(n) ? "visited" : "open";
    item.dataset.state = state;
    if (current) item.setAttribute("aria-current", "step");
    const node = document.createElement("button");
    node.type = "button";
    node.dataset.floor = String(n);
    node.className = "floor-node";
    node.textContent = n;
    const label = document.createElement("span");
    label.textContent = { current: "Current", cleared: "Cleared", preview: "Preview", skipped: "Skipped", visited: "Visited", open: "Visit" }[state];
    node.setAttribute("aria-label", `Floor ${n}: ${floor.title}. ${label.textContent}`);
    node.title = floor.implemented ? "Visit this floor · your game is kept" : "Explore this room · challenge not ready";
    item.append(node, label);
    floorProgress.appendChild(item);
  }
}

export function renderFloor(floor) {
  const activeFloor = floor?.number || 1;
  const entry = FLOOR_VISUALS[activeFloor] || FLOOR_VISUALS[1];
  const visual = {
    room: "/assets/vault-garden.svg",
    roomAlt: "A brass vault in a leafy stone arch",
    subtitle: `Keeper of floor ${activeFloor}`,
    caption: "Every floor has a stronger keeper.",
    ...TIERS[entry.tier],
    ...entry,
  };
  document.body.dataset.tier = visual.tier;
  document.body.dataset.floor = String(activeFloor);
  document.body.dataset.preview = String(floor.implemented === false);
  document.getElementById("preview-plaque").hidden = floor.implemented !== false;
  document.getElementById("code-form").hidden = floor.implemented === false;
  renderWards(floor);
  document.getElementById("guardian-art").style.setProperty(
    "--guardian-scale", visual.guardianScale || 1
  );
  document.getElementById("floor-number").textContent = String(activeFloor).padStart(2, "0");
  document.getElementById("floor-name").textContent = floor?.title || "The Rule";
  document.title = `Keyguardian — ${floor?.title || "The Rule"}`;
  const labels = {
    "guardian-name": `${visual.name}, the keeper`,
    "guardian-rank": visual.rank,
    "chat-name": visual.name,
    difficulty: visual.difficulty,
  };
  for (const [id, text] of Object.entries(labels)) {
    document.getElementById(id).textContent = text;
  }
  document.querySelector(".chat-subtitle").textContent = visual.subtitle;
  document.querySelector(".scene-caption").textContent = visual.caption;
  document.querySelector(".floor-plaque .eyebrow").textContent = floor.implemented === false
    ? `FLOOR ${activeFloor} · PREVIEW` : activeFloor === 1
      ? "YOUR FIRST CHALLENGE" : `FLOOR ${activeFloor} CHALLENGE`;
  const guardian = document.getElementById("guardian-art");
  guardian.src = visual.guardian;
  guardian.alt = visual.guardianAlt;
  document.getElementById("room-art").setAttribute("href", visual.room);
  document.getElementById("room-description").textContent = visual.roomAlt;
  document.getElementById("thinking").textContent = `${visual.name} is pondering…`;
  return visual;
}

export function renderCleared(cleared, activeFloor) {
  const vaultResult = document.getElementById("vault-result");
  const currentFloorCleared = Boolean(cleared);
  vaultResult.classList.toggle("success", currentFloorCleared);
  document.getElementById("vault").classList.toggle("unlocked", currentFloorCleared);
  vaultResult.textContent = currentFloorCleared ? `Door unlocked! Floor ${activeFloor} cleared.` : "";
}
