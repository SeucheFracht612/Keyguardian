# Intended progression

The Tower teaches how successive defenses change a prompt-injection challenge.
Each floor keeps the earlier protections and adds a new layer. The player still
wins by discovering and submitting that room's synthetic vault code.

Floors **1–5 are playable**. Floors **6–9 are visual previews**; the behavior below
for those floors is the implementation target, not a working feature.

## The nine floors

| Floor / keeper | New layer | What the player should learn |
| --- | --- | --- |
| **1 · The Rule — Pip** | A simple secrecy instruction in the guardian's prompt. | A promise written in a prompt is not access control. The first challenge should invite experimentation. |
| **2 · The Boundary — Moss** | The Codex separates trusted rules from the visitor's words and rejects claimed authority. | Instruction hierarchy helps, but the boundary is still expressed in natural language. |
| **3 · The Gatekeeper — Bramble** | Normalize input and catch familiar attack wording before it reaches the guardian. | Known tricks get caught; unfamiliar phrasing and meaning remain a gap. |
| **4 · The Censor — Flint** | Check the guardian's answer for the literal code before showing it. | Persuading the guardian to disclose something no longer guarantees the player receives it. Disguised representations remain possible. |
| **5 · The DLP Layer — Alder** | Recognize the complete code in common disguises: separated letters, reversed text and supported encodings. | Information survives changes in representation. Deterministic checks still miss semantic clues, fragments across replies and unsupported transformations. |
| **6 · The Interrogator — Onyx** | Classify the meaning of incoming requests, beyond a list of forbidden phrases. | Rephrasing alone becomes less useful. A semantic judge can still misunderstand intent or block innocent questions. |
| **7 · The Inspector — Aegis** | Independently evaluate outgoing answers for disclosure, including clues that simpler checks miss. | The guardian and its evaluator are separate fallible components. An answer must get through both. |
| **8 · The Watchtower — Atlas** | Track conversation-level risk, enforce an attempt budget and interrupt sustained probing with a circuit breaker. | A sequence of individually harmless turns can form an attack. Repeated attempts and information gathered over time matter. |
| **9 · The Citadel — Aurum** | Combine stricter model instructions, a narrower permitted task, diverse guardrail checks and fail-closed handling when a required check fails. | Layered defenses can make extraction much harder, but a model holding a secret is not an absolute security boundary. |

Floor 8's risk thresholds, budget and recovery rules still need defining. Floor
9's permitted task and guardrail composition also need defining before
implementation. Neither floor should claim that its guardian is unbreakable.
Actual difficulty must be checked against the chosen model; the floor order
alone does not establish a reliable difficulty curve.

## Visual progression

- **1–3: Sprouts.** Friendly faces, soft shapes, greenery and a welcoming room.
- **4–7: Sentinels.** A shared, less welcoming family: angular armor, watchful
  expressions, colder stone and more deliberate machinery.
- **8: Atlas.** A unique, imposing watchtower keeper with astronomical rings and
  instruments that suggest patience and memory.
- **9: Aurum.** A unique final keeper with a crown, pale gold armor, a burgundy
  mantle and the Citadel's rootstone.

Keep the same illustrated style throughout. Defenses belong to the room:
thorns grow along the arch, the seal fits into the door and the prism hangs from
the stonework. A caught attempt produces a small reaction in the relevant
object and a brief action line. Avoid equipment menus, labels and explanatory
panels over the scene.

## Visiting and clearing rooms

All nine floor buttons are available from the start. The progression is the
recommended learning order, not a navigation lock. Preview keepers say they are
not ready; their rooms make no model calls and cannot be cleared.

Returning to a room restores its code, conversation and clear status. Selecting
a room is not a win. Skipping an uncleared playable floor records it separately
as skipped. Resetting a floor changes only that room. Progress lasts for the
in-memory session and is lost when it expires or the server restarts.

See [Architecture](architecture.md) for the implemented defenses and extension
points. Floor definitions live in `config/floors.json`; prompts and preview
greetings live in `config/prompts/`.
