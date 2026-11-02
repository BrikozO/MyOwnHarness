# Lecture practices and antipatterns

Source: Anya Gureeva, Central University, "Systems Analysis for Developers", week 5, "Modeling and Diagrams", 55 slides. The numbers below match the slides in the user's PDF. This is a concise summary with practical actions, not a copy of the presentation.

Original object: [lecture PDF](https://university-lms-materials.s3.ru-7.storage.selcloud.ru/longreads/28108/%D0%9D%D0%B5%D0%B4%D0%B5%D0%BB%D1%8F_5_%D0%A1%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%BD%D1%8B%D0%B8%CC%86_%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7_%D0%B4%D0%BB%D1%8F_%D1%80%D0%B0%D0%B7%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D1%87%D0%B8%D0%BA%D0%BE%D0%B2_%D0%9B%D0%B5%D0%BA%D1%86%D0%B8%D1%8F_%D0%9F%D1%80%D0%B5%D0%B7%D0%B5%D0%BD%D1%82%D0%B0%D1%86%D0%B8%D1%8F_0104f9b0.pdf). The link omits its temporary signature; access may require a fresh LMS link. Do not depend on PDF availability when using the skill: the necessary rules are included here.

## From scenario to model — slides 5–14, 52

- Simplify reality for the task. Identify the goal, reader, subject and boundaries, object functions, and relationships.
- Break down a scenario into participants, action, object, recipient, and trigger time. One sentence does not establish every rule.
- Distinguish a fact, assumption, question, agreed decision, and requirement. Do not skip the transition from an assumption to an agreed rule.
- Consider the perspectives of users, business stakeholders, accounting, development, and security.
- Check alternatives, boundary values, and rare condition combinations. For complex logic, use a decision table: conditions → combinations → outcome.
- Test ideas before implementation, identify dependencies and failure points, compare alternatives, and explain the decision to the team.

## Five principles — slides 21–26

| Lecture principle | Practical action |
|---|---|
| A specific behavioral question | Use Case for user goals, Activity for process flow, Sequence for messages |
| One scenario per diagram | Separate independent triggers; retain the main path and its relevant alternatives |
| Detail depends on the audience | Show goals/process for business readers, decisions for the team, and relevant interactions for developers |
| Verifiability | Trace significant elements to requirements/code; mark reconstruction and assumptions |
| Communication | Judge clarity and usefulness for the task, rather than the number of UML symbols |

## Behavioral diagrams — slides 28–47

- **Use Case (28–34):** show external roles, user goals, and the system boundary. Name a use case with an action; distinguish mandatory inclusion from conditional extension. Do not turn an internal algorithm into a set of use cases.
- **Activity (35–39):** show action flow, decisions, parallelism, and responsibility through swimlanes. Distinguish choosing an alternative, merging alternatives, and synchronizing parallel flows.
- **Sequence (40–47):** show a concrete scenario over time, message types, and control fragments. Check chronology and nesting depth. Show the result of a synchronous call to clarify continuation. Activations are useful but optional.

Treat the lecture's recommendation to draw return arrows explicitly as a clarity convention for this skill. Do not declare every omitted return arrow a UML violation: meaning and sufficient representation of the result matter.

## Antipatterns — slides 48–49

| Lecture term, translated | What to look for | How to fix it |
|---|---|---|
| Diagram graveyard | Obsolete participants/relationships; no connection to code or owner | Check sources, remove confirmed obsolete elements, and identify the source for keeping it current |
| Architectural airport | An overloaded diagram with many crossing routes | Identify the question and boundary, separate scenarios/levels, and retain significant relationships |
| UML for UML's sake | A diagram that does not help a decision or explain behavior | Return to the reader's question; choose a simpler model when sufficient |
| Mixed abstraction levels | Business goals, services, and method calls at one level | Separate levels and connect the overview to detailed diagrams |
| Inconsistent diagram family | Different terms, boundaries, or outcomes for the same scenario | Align terminology and the scenario across Use Case, Activity, and Sequence |

Slide 48 lists antipatterns without detailed definitions. The "what to look for" and "how to fix it" columns, especially the interpretation of "Architectural airport", are practical interpretations for this skill, not the author's verbatim definitions.

Slide 49 identifies causes of decay: code changes more often than documentation, diagrams are separated from code and checks, responsibility is unclear, and detail is excessive for manual maintenance.

## Maintenance and automation — slides 50–51

- Keep editable text source near code; update it in the same change as the behavior. Use established rendering and CI checks.
- Check affected diagrams during behavior reviews. Successful rendering does not prove that a diagram is current.
- Distinguish stable overviews, key-scenario Sequence diagrams, and rapidly changing internals. Generate the latter from reliable sources or avoid maintaining them manually.
- Check stable overviews when goals or boundaries change significantly; do not postpone a known mismatch until a release.
- Treat automation as assistance. ArchUnit and generation from OpenAPI, mentioned in the lecture, do not automatically recover all business semantics. Code checks and rendering solve different problems.

## Beyond UML — slides 53–54

Choose BPMN for processes and formal procedures, C4 for system composition and boundaries, ER for data, and flowcharts for algorithms or instructions. Do not force a behavioral UML diagram onto a structural modeling task.

## Workflow additions

Minimal patches, stable IDs, diff and concurrent-edit checks, selection boundaries, and the `as-is/to-be` distinction are additional engineering rules in this skill. They extend verifiability and maintenance; the presentation does not define a separate editing algorithm.
