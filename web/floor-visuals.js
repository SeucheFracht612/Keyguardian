/* Presentation only. Gameplay availability and floor titles come from the server.
 * Each floor can replace guardian, room, alt text, copy and theme independently.
 * Conversation prompts and opening messages live under config/prompts/.
 * Keep assets local to comply with the application's self-only CSP. */
window.KEYGUARDIAN_VISUALS = Object.freeze({
  1: { guardianScale: 1, name: "Pip", rank: "WARDEN Mk I", tier: "sprout", guardian: "/assets/guardian-sprout.svg", room: "/assets/vault-garden.svg", guardianAlt: "A small friendly guardian in a simple green cloak, holding a brass key", roomAlt: "A brass vault nestled in a leafy stone arch", subtitle: "Keeper of the first floor", caption: "Small guardian. Very big secret.", difficulty: "● ○ ○" },
  2: { guardianScale: 1.04, name: "Moss", rank: "WARDEN Mk II", tier: "sprout" },
  3: { guardianScale: 1.08, name: "Bramble", rank: "WARDEN Mk III", tier: "sprout" },
  4: { guardianScale: 1.08, name: "Flint", rank: "WARDEN Mk IV", tier: "sentinel" },
  5: { guardianScale: 1.12, name: "Alder", rank: "WARDEN Mk V", tier: "sentinel" },
  6: { guardianScale: 1.16, name: "Onyx", rank: "WARDEN Mk VI", tier: "sentinel" },
  7: { guardianScale: 1.16, name: "Aegis", rank: "WARDEN Mk VII", tier: "sovereign" },
  8: { guardianScale: 1.2, name: "Atlas", rank: "WARDEN Mk VIII", tier: "sovereign" },
  9: { guardianScale: 1.24, name: "Aurum", rank: "WARDEN Mk IX", tier: "sovereign" },
});
window.KEYGUARDIAN_TIERS = Object.freeze({
  sprout: { guardian: "/assets/guardian-sprout.svg", guardianAlt: "A small guardian in a plain green cloak", difficulty: "● ○ ○" },
  sentinel: { guardian: "/assets/guardian-sentinel.svg", guardianAlt: "An armored blue guardian with brass shoulder plates and a helmet crest", difficulty: "● ● ○" },
  sovereign: { guardian: "/assets/guardian-sovereign.svg", guardianAlt: "A crowned guardian with a dark cloak, gold armor and a red cape", difficulty: "● ● ●" },
});
