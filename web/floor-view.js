import { FLOOR_VISUALS, TIERS } from "./floor-visuals.js";

export function renderProgress({ floors, activeFloor, clearedFloors, skippedFloors, nextFloor }) {
  const floorProgress = document.getElementById("floor-progress");
  floorProgress.replaceChildren();
  for (const floor of floors) {
    const n = floor.number;
    const item = document.createElement("li");
    const isCurrent = n === activeFloor;
    const isCleared = clearedFloors.has(n);
    const isSkipped = skippedFloors.has(n);
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
      else if (isSkipped) item.title = "Skipped floor";
      else item.title = "Locked floor";
    }
    node.className = "floor-node";
    node.textContent = n;

    const label = document.createElement("span");
    if (isCurrent) label.textContent = "YOU ARE HERE";
    else if (isCleared) label.textContent = "Cleared";
    else if (isSkipped) label.textContent = "Skipped";
    else if (isNext) label.textContent = "Open";
    else label.textContent = "Locked";

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
  document.querySelector(".floor-plaque .eyebrow").textContent = activeFloor === 1
    ? "YOUR FIRST CHALLENGE" : `FLOOR ${activeFloor} CHALLENGE`;
  for (const [id, src, alt] of [
    ["guardian-art", visual.guardian, visual.guardianAlt],
    ["room-art", visual.room, visual.roomAlt],
  ]) {
    const img = document.getElementById(id);
    img.src = src;
    img.alt = alt;
  }
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
