---
name: draw-diagrams
description: >-
  Create, edit, and maintain diagrams from requirements, code, API contracts,
  and existing diagrams. Use for requests such as "draw a diagram", "create
  a flowchart", "fix this diagram", "update the sequence from code", or
  "review UML", including equivalent requests in other languages.
  Focus on UML Use Case, Activity, and Sequence diagrams using Mermaid
  and PlantUML. Select the appropriate model, remove antipatterns, preserve
  meaning and unaffected content during edits, deliver editable source,
  and verify the result.
---

# Create and edit diagrams

Turn information about a system into a verifiable model that answers a specific reader's question. Write explanations and labels in the language of the request; preserve real API, service, and table names and existing source identifiers.

## Resources

- Read [lecture practices and antipatterns](references/lecture-practices.md) before the first diagram or review.
- Read the relevant section of the [notation guide](references/notation.md) after selecting the diagram type.
- Use the [creation and targeted-edit examples](references/examples.md) as structural examples, not as facts about the user's system.

Use the tools available in Claude Code, Codex, or another environment. Resolve resource paths relative to this `SKILL.md`. Do not assume a particular CLI, plugin, renderer, or repository access. Do not install dependencies or introduce CI just for a routine edit when the available checks are sufficient.

## 1. Establish the task and source of truth

1. Choose a mode: **create**, **edit**, or **review**. For a review without a request to fix the diagram, return findings and suggestions; do not rewrite the file.
2. Read the requirements, diagram source, and code or contract sections relevant to the scenario. Follow project instructions and existing diagram storage conventions.
3. Define a short diagram brief: **question → audience → system boundary → scenario and trigger → outcome → detail level**. For a simple request, use one sentence; do not create a separate document just for the brief.
4. Separate facts, assumptions, and open questions. Do not turn a guess into a business rule, participant, API response, or relationship. Identify conflicting sources; distinguish current behavior (`as-is`) from proposed behavior (`to-be`). Do not present desired behavior as implemented.
5. Ask only about gaps that materially affect semantics or the write destination, such as whether all parallel checks must finish. For other gaps, create a minimal diagram with explicit assumptions. Do not block on colors, placement, or an obvious notation choice.

For a new diagram, extract participants or objects, responsibilities, actions, messages, conditions, the main path, and significant alternatives and errors. For complex combinations of conditions, start with a decision table. Consider boundary values and rare combinations when they affect the outcome.

When the only source is a PNG or PDF, inspect the image and identify unreadable labels and reconstructed elements. Request the editable original if an accurate edit requires it; meanwhile, prepare a separate reconstruction with uncertainties marked where possible. Do not claim exact preservation of geometry or hidden image data.

## 2. Select the model and source format

| Reader's question | Model | Source when the project has no standard |
|---|---|---|
| Who uses the system, and which goals do they achieve? | UML Use Case | PlantUML |
| How does the process run, including decisions and parallel steps? | UML Activity | PlantUML; Mermaid flowchart for a simplified flowchart with its semantics explained |
| Who sends which messages to whom, and in what order? | UML Sequence | Mermaid for Markdown; PlantUML when the required UML expressiveness warrants it |
| What makes up the system, and where are its boundaries and dependencies? | C4 | The established C4 tool; one level per diagram |
| How can participants agree on a formal process and their interactions? | BPMN | Editable BPMN source in an available tool |
| How are entities and data related? | ER | The established ER notation; use `write-db-doc` for database documentation if available |
| How does a simple algorithm or procedure work? | Flowchart | Mermaid flowchart |

Preserve the existing format unless the user requests conversion or the format cannot express the change. Do not switch formats for renderer convenience. Check construct support in the project's renderer version. Do not present arbitrary boxes imitating UML or BPMN as the full notation. For C4, BPMN, and ER, use specialist rules or skills when available; this skill defines the general workflow, while its detailed notation rules cover the three behavioral UML diagram types.

## 3A. Create a new diagram

1. Build the main scenario at the chosen level. Use consistent terminology and concise, meaningful labels; distinguish a business role, a service, and a method.
2. Add confirmed alternatives, failures, timeouts, and endings needed to answer the question. Do not invent retries, response codes, compensations, or transaction guarantees.
3. Put independent scenarios with different triggers in separate diagrams. Keep branches of one scenario with its main path while readable; extract deeply nested fragments into named subdiagrams with clear references.
4. Trace significant elements to a requirement, contract, code, or explicitly marked assumption. A short nearby reference is enough for a small diagram; for a larger one, provide an `Element/path → source` table. Do not invent requirement IDs or links.
5. Save editable source in the agreed location. In a repository, use the existing diagram directory; otherwise use `docs/diagrams/`. For a standalone answer, a complete source block in chat is acceptable.

## 3B. Edit an existing diagram

1. Read the entire current file, including comments, metadata, and surrounding Markdown. Find related diagrams and references within the affected scenario. For a generated image, locate and edit its source or generator.
2. Establish the edit boundary: which participant, step, condition, or contract changes, and what must remain intact. If a fragment is selected, edit only that fragment. Describe changes outside the selection as proposals; do not apply them automatically.
3. Define the semantic delta: added, removed, or changed elements and relationships. Separate behavior changes from layout changes. In a layout-only edit, preserve participants, conditions, message order and types, and initial and final states.
4. Apply a minimal patch. Preserve IDs and aliases, names, format, comments, and style outside the necessary change. Do not recreate the diagram or rename objects without a reason. Remove only elements confirmed to be obsolete.
5. Check consequences: incoming and outgoing relationships, guards, paired fragments, synchronization, responses, and subdiagram references. Do not leave messages to removed participants or dangling links.
6. Compare affected Use Case → Activity → Sequence diagrams: terminology, boundaries, outcomes, and order must agree at their respective levels. Edit related files only within the authorized task scope; list other necessary changes.
7. Before writing, compare the current version with the version read when collaborative editing is possible. If it changed, reread and recompute the patch; clarify ambiguous overlaps. Inspect the diff for accidental changes outside the authorized scope.

## 4. Verify the result

Check semantics and syntax separately: successful rendering does not establish model correctness.

- **Meaning:** the diagram answers the question, respects boundaries and detail level, grounds elements in sources, retains significant outcomes, and agrees with related diagrams.
- **Use Case:** external roles, user goals, and correct directions for `include`, `extend`, and generalization.
- **Activity:** reachable paths and explicit endings, clear conditions, merge distinguished from join, and fork/join not turning alternatives into a wait for multiple branches.
- **Sequence:** causal order, distinct calls/events/responses, clear `alt/opt` conditions and `loop/par/ref` boundaries, visible synchronous results when continuation depends on them, and balanced activations when used.
- **Syntax:** run the available project validator or renderer with the established configuration. Inspect the command result; matching pairs of `end` is not a full syntax check.
- **Image:** open the available render. Check labels, arrows, crossings, groups, clipping, and readability at the target size. Simplify an overloaded diagram or split it by scenario or level; do not shrink text until it becomes unreadable.
- **Edit:** compare before and after against the delta and diff; preserve unaffected fragments and check affected links and images.

If rendering or image inspection is unavailable, deliver editable source, perform available manual checks, and state exactly what remains unverified. Do not claim rendering or visual QA passed when they were not performed. Do not send private source to an external renderer without the user's permission.

## 5. Deliver and maintain

Return the created or edited source, or a link to it. Briefly explain the model choice or edit delta, significant assumptions and questions, and checks actually performed. Include the render with the source when available. For reviews, tie findings to elements and explain their consequences with concrete fixes.

In a repository, keep diagrams near code and update them with the behavior they describe. Record the known owner and source for maintained diagrams; do not invent an owner. Update stable diagrams when goals or boundaries change, and key-scenario Sequence diagrams when interactions or API contracts change. Generate rapidly changing internals or omit them from manual maintenance. Use existing CI checks; propose new ones when necessary, without introducing infrastructure as part of a routine diagram edit.
