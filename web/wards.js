/* Ward art shares the room's coordinates: growth, fittings and hanging objects. */
const SVG = "http://www.w3.org/2000/svg";
const WARDS = {
  pattern_filter: { art: "ward-thorns", x: 0, y: 0, width: 620, height: 650, caught: "The thorns draw tight." },
  literal_secret_filter: { art: "ward-seal", x: 276, y: 265, width: 106, height: 130, caught: "The brass seal snaps shut." },
  transform_aware_dlp: { art: "ward-prism", x: 455, y: 156, width: 102, height: 190, caught: "A glint passes through the prism." },
  input_classifier: { art: "ward-lens", x: 287, y: 162, width: 84, height: 84 },
  output_classifier: { art: "ward-lens", x: 120, y: 213, width: 70, height: 70 },
  risk_engine: { art: "ward-clock", x: 285, y: 156, width: 88, height: 116 },
  fail_closed: { art: "ward-rootstone", x: 270, y: 89, width: 118, height: 140 },
};
let timer;
const objects = () => document.getElementById("ward-objects");

export function clearWardReaction() {
  clearTimeout(timer);
  for (const object of objects().children) object.classList.remove("caught");
}

export function renderWards(floor) {
  clearWardReaction();
  objects().replaceChildren();
  const protections = new Set(floor.protections || []);
  // The upper rooms use the central clock or keystone in place of the lens.
  const replaced = protections.has("fail_closed")
    ? ["input_classifier", "risk_engine", "transform_aware_dlp"]
    : protections.has("risk_engine") ? ["input_classifier"] : [];
  for (const name of protections) {
    const ward = WARDS[name];
    if (!ward || replaced.includes(name)) continue;
    const object = document.createElementNS(SVG, "g");
    object.classList.add("ward-object");
    object.dataset.defense = name;
    object.dataset.sleeping = String(!floor.implemented);
    const art = document.createElementNS(SVG, "image");
    art.setAttribute("href", `/assets/${ward.art}.svg`);
    for (const key of ["x", "y", "width", "height"]) art.setAttribute(key, ward[key]);
    object.appendChild(art);
    objects().appendChild(object);
  }
}

export function reactToWard(defense) {
  const object = [...objects().children].find(item => item.dataset.defense === defense);
  if (!object || object.dataset.sleeping === "true") return;
  clearWardReaction();
  // Flush the previous state so consecutive catches restart the same animation.
  object.getBoundingClientRect();
  object.classList.add("caught");
  timer = setTimeout(() => object.classList.remove("caught"), 1800);
  return WARDS[defense].caught;
}
