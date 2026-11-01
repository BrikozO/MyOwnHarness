---
name: "write-db-doc"
description: Database documentation in Russian, written like a systems analyst and anchored to ГОСТ Р 59795-2021 / ГОСТ 34 — «Описание базы данных», логическая структура, словарь данных (data dictionary), entities, attributes, relationships, plus an ER diagram. Input is SQL DDL (pg_dump, migrations, CREATE TABLE), a schema dump, an ER picture or a verbal description; PostgreSQL first, MySQL and MS SQL too. Use it whenever someone asks to document or describe a database, schema or tables («опиши БД», «опиши таблицы», «задокументируй схему», «сделай словарь данных»), write a DB section of a технический проект or wiki page, draw an ER diagram from DDL, or write «описание организации информационной базы» — even if GOST is not mentioned.
---

# write-db-doc: database design documentation per GOST, written like a systems analyst

The skill turns DDL into a document from which a team understands its data: what is stored, what each field means, how entities are linked, which rules the schema enforces and where it is weak. Sections follow ГОСТ Р 59795-2021, the text is in information style, and an ER diagram is always attached.

**Language.** These instructions are in English. The document itself — headings, text, tables, captions, open questions, the diagram title, legend and link verbs — is always written in **Russian**. Database identifiers stay in **English** everywhere they appear: table and column names in the diagram boxes, in attribute tables and in the text (`order.client_id`). Reference files give ready-made Russian headings and phrasings; use them.

Three principles behind the skill:

1. **An analyst, not a DDL stenographer.** The DDL already lists the columns. The document adds what the DDL does not have: meaning, rules, links in business terms, reasons behind decisions and their consequences. An attribute table without meaning is a printout of the schema, not documentation.
2. **GOST is the frame, not the style, and not a citation.** Sections and their content come from ГОСТ Р 59795-2021 (п. 8.9 «Описание базы данных», п. 8.5.2 logical structure, physical structure, maintenance). Neither the bureaucratic language such documents are usually written in nor references to the standard are taken along: the document follows GOST without mentioning it.
3. **Never invent.** If a field's meaning cannot be derived from a database comment, the name, constraints or the user's words, write the obvious and move the question to «Открытые вопросы». An invented description is worse than an empty one: people will trust it.

## Reference files

- `references/gost-structure.md` — the document template, what GOST requires in each section, variants («Описание организации информационной базы», «только логическая структура»), formatting. Read before writing.
- `references/style.md` — writing style: information style («Пиши, сокращай»), Ramalho's way of explaining, stop words, before/after examples and a table of ready Russian phrasings. Read before writing.
- `references/er-diagram.md` — diagram rules, `labels.json`, commands, how to check the picture. Read before drawing.

Scripts (Python 3; the parser and checks need only the standard library):

| Script | What it does |
|---|---|
| `scripts/parse_ddl.py` | DDL → `model.json` (tables, columns, keys, links, indexes, comments, enums, views, critical problems, possible logical links) and `summary.md`, a draft data dictionary in Russian |
| `scripts/render_er.py` | `model.json` + `labels.json` → ER diagram SVG and PNG with orthogonal lines from PK rows to FK rows; logical links without FK are dashed |
| `scripts/lint_style.py` | finds Russian stop words and long sentences |
| `scripts/check_coverage.py` | checks the draft against the model: every table and column described, no references to non-existent columns, a diagram embedded |

Use this workflow in Claude Code or Codex with the available file, shell, image and document tools. Resolve bundled resources relative to this SKILL.md, never relative to a hard-coded installation folder. Check for a Python 3 interpreter before executing scripts; `python3` below is an example and may need replacing with the available interpreter. If local execution or file access is unavailable, use a supported workspace/runtime that can run the bundled scripts; otherwise report which parsing, rendering and validation steps could not run, and never claim they passed. Keep the same Russian document structure and output format.

In the commands below `$SKILL_DIR` is the folder this SKILL.md lives in; substitute the absolute path (the scripts are not on PATH and the working directory is usually elsewhere). Two kinds of files come out of the run. Deliverables — the document and the diagrams it embeds (PNG, plus SVG) — go wherever the document goes. Intermediates — `model.json`, `summary.md`, `labels.json`, the draft — stay in the scratch/working folder, not in the user's folders, unless the user asks for them.

Before the first render, check PNG support with the selected interpreter (`python3 -c "import cairosvg"`) or the available-command lookup for `rsvg-convert`. If neither is available and dependency installation is supported, use a project or temporary virtual environment (`python3 -m venv <scratch>/venv`, then its interpreter with `-m pip install cairosvg`); do not modify system Python. If installation is unavailable or fails, deliver SVG and state that PNG could not be produced.

## Process

### 0. Decide what and where

- **Which document.** By default «Описание базы данных» per п. 8.9, with logical and physical structure. If asked for «описание организации информационной базы» or «только логическая структура для техпроекта», see the variants in `gost-structure.md`.
- **Where it goes.** This skill decides the content; the environment decides the container. Use the current environment's supported document-creation mechanism and document/format skills when available, following its rules about document creation order, files and attachments. Do not require one vendor's document tool or hard-coded output folder. Preserve the GOST-based section structure and the user's chosen destination and format, and only add this:
  - The user named a wiki or tracker (Confluence, Notion, Outline, YouTrack, GitLab/GitHub wiki) — publish there through its tool if one is available; if the space or parent page is not given, ask. If no tool can reach it, produce the document in the default way and say what would let you publish it.
  - The user named a file format (Markdown, .docx) — produce that file.
  - In a code repository with a `docs/` folder or similar — a Markdown file there is often the natural home; ask if unsure.
  - Keep a local Markdown draft for the checks in step 5, using a scratch folder supported by the environment. If the destination requires creating an empty document before drafting, do that first, then prepare and check the draft before filling the document. Do not overwrite an existing destination without reading it.
- **Context.** System name, domain, readers. If something is missing, do not stop for it: take the name from the schema or file, list assumptions at the top of the document, collect questions for «Открытые вопросы». Ask up front only what would send the result to the wrong place (e.g. the wiki space).

### 1. Parse the DDL

```bash
python3 "$SKILL_DIR/scripts/parse_ddl.py" <files.sql or migrations folder> -o model.json --summary summary.md
```

Read `summary.md` in full — it is the draft data dictionary. Check `warnings` and `skipped_statements` in `model.json`: if the parser missed something (exotic syntax, triggers, functions), read that DDL fragment yourself. Triggers and functions are skipped by the parser, and business rules often live there (setting `updated_at`, changing statuses) — read them and describe the rule in words.

Pass a migrations folder as a whole: the parser applies the files in order and returns the final state. PostgreSQL keeps the case of non-Latin names (`Клиент` stays `Клиент`); the parser does the same.

### 2. Understand the domain

Before writing, answer for yourself:
- Which **domain objects** stand behind the tables? An object is a business concept («Сделка»); several tables may serve one object.
- How does the schema split into **subject areas** («Клиенты», «Продажи», «Справочники»)? They drive section 2, the entity list and the diagram split.
- What kind is each table: main, reference, link (M:N), log? `role_hint` in the model is a hint; check it by meaning.
- Where is a **life cycle** (statuses, stages, close dates) and what enforces it (CHECK, enum, triggers)?
- Which columns reference other tables **without a FK** (logical links)? Check `logical_link_candidates` and the names yourself.
- Where is behaviour easy to get wrong (cascade deletes, timestamps without time zone next to ones with it, composite keys of partitioned tables)? Describe it as fact in the entity's subsection.
- Is anything in `critical`? It gets a «⛔ Критично» callout; nothing else does.

Write `labels.json` (format in `er-diagram.md`):
- `entities` — short Russian entity names (`{"crm.deal": "Сделка"}`) for the text; the diagram itself shows only table names;
- `links` — a Russian verb per foreign key that reads from parent to child (`{"deal.company_id": "заключает"}` → «Компания заключает сделки»).
- `logical` — links without a FK that are evident from names, types, comments or the user's words (`[{"child": "orders.customer_id", "parent": "customers.id", "label": "оформляет"}]`). Start from `logical_link_candidates` in the model, keep only those that make sense; drawn dashed.

Use the same names and verbs in the text and in the relationships table: one concept, one word.

### 3. Draw the ER diagram

Rules and commands are in `references/er-diagram.md`. In short:

```bash
python3 "$SKILL_DIR/scripts/render_er.py" model.json -o er_full.svg --labels labels.json --title "<Система>: логическая структура БД"
```

- Lines are straight and orthogonal (horizontal and vertical segments only), leave the parent's PK row and enter the child's FK row, parents on the left, children on the right, Russian verb labels beside their lines. Boxes are square-cornered and contain only English identifiers: table name, columns, types. The script does this; do not replace it with PlantUML, Mermaid or Graphviz — none of them can anchor right-angled lines to rows.
- Up to 15 entities — one detailed diagram; more — an overview (`--keys-only`) plus one per subject area (`--tables`).
- **Open the PNG with an available image tool and inspect it.** If image inspection is unavailable, state that visual QA remains unverified; do not claim it passed. No line over a box or text, labels next to their own lines and off the markers, no small steps, not wider than ~1800 px. If not, split by subject area or give a layout hint in `labels.json` and render again.
- No PNG even after the install attempt above: deliver the SVG and say so.

### 4. Write the document

Follow the template in `references/gost-structure.md` and the style in `references/style.md`. The essentials:

- **First sentence about an entity — what one row is.** «Одна строка — одна сделка с компанией.» Then who creates and changes rows and when, if known.
- **Attribute table** for every entity, every column without exception: Атрибут | Тип | Обяз. | Ключ | Описание. The description gives meaning, units, format, allowed values, who sets the default. Not «Поле содержит дату», but «Дата закрытия сделки; заполняется при переходе в `won` или `lost`».
- **Links at the attribute level** as a separate table: parent.PK → child.FK, cardinality, optionality, on delete/update, meaning with the same verb as on the diagram. Logical links without FK go into the same table («логическая связь, СУБД не контролирует») and onto the diagram as dashed lines.
- **Explain why** where a decision is not obvious, and only when the reason is known or follows directly from the schema.
- **Example queries** where it is unclear how to use the data (link tables, life cycles, partitions, hierarchies). Names strictly from `model.json`.
- **Callouts** «Внимание» for risk of losing or corrupting data (cascade delete, missing check, missing partition), «Примечание» for a useful detail, «Совет» for a handier way to work.
- **No review section, and «⛔ Критично» only for breaking problems.** The document records the schema, it does not review it: no «Замечания к схеме», no improvement proposals — readers would mistake opinions for facts about the system, and review is a separate task. The single exception is a problem that breaks the schema or a table (`critical` in the model); exact criteria and wording are in `gost-structure.md`, «Критично» callouts.
- **Open questions** numbered and concrete, referenced from attribute descriptions («уточнить, вопрос 4»).
- **The diagram** in 3.1: the PNG with the caption «Рисунок N — …» and a sentence on how to read it.
- **The standard stays invisible in the document.** GOST shapes the structure and the content of sections; the document itself never names it: no «ГОСТ Р 59795-2021», no clause numbers («п. 8.9»), no «согласно ГОСТ», no standards in «Связанные документы», no remarks like «сверьте с текстом стандарта». A reader recognises the structure without being told, and clause numbers only add noise and a claim someone then has to verify. Add references only if the user explicitly asks for them. «Связанные документы» lists only real project documents; if there are none, leave the subsection out.

Write the draft to a Markdown file first, so the scripts can check it before publishing. For a big schema write section by section, not in one go.

### 5. Check

```bash
python3 "$SKILL_DIR/scripts/check_coverage.py" model.json draft.md
python3 "$SKILL_DIR/scripts/lint_style.py" draft.md
```

- `check_coverage.py` must pass: every table and column described with a non-empty description, no references to non-existent columns, the diagram embedded, no references to standards (add `--allow-standard-refs` only when the user asked for them).
- `lint_style.py` — go through every hit. A stop word is a reason to reread the phrase, not an order: keep terms («данные», «уникальный ключ», «информационное обеспечение», «многие ко многим»).
- Reread as a developer would: is every «where is X stored» and «what happens if I delete Y» answered within a minute?

### 6. Deliver

Move the checked draft into the container chosen in step 0, following that container's own rules for content and images. Whatever it is:

- The diagram is embedded as an image in 3.1 (PNG, uploaded the way the container expects), with its caption — not only attached. The SVG goes along when the user may want to edit or print it.
- Files keep readable names: `<name>_описание_БД.md` (or .docx), `er_*.png`, `er_*.svg`.
- If the container changed the text (formatting, image links), run `check_coverage.py` on what it holds when you can read it back.

In the chat reply — two or three sentences in Russian: what was produced (how many entities and links described, how many of them logical), critical problems if any, how many open questions, what to do next (e.g. answer the questions and add `COMMENT ON` to the database). Do not repeat a link that a card already shows.

## Common situations

- **No comments in the database.** Rebuild descriptions from names, types, constraints and links, honestly: say in «Допущения» that descriptions were reconstructed and need review, and mark non-obvious fields with questions. In the chat reply, offer `COMMENT ON ...` statements once answered — that puts the knowledge back into the database.
- **Very big schema (50+ tables).** Ask whether to describe everything or chosen subject areas. If everything: overview diagram, one diagram per subject area, entities grouped by area; write area by area and show the user the first one before doing the rest.
- **Only a verbal description or an ER picture, no DDL.** Write a minimal DDL by hand from it (`CREATE TABLE` with types, `NOT NULL`, `PRIMARY KEY`, `REFERENCES`) with **English snake_case identifiers**, even if the picture uses Russian names: «Номер_заказчика» → `client_id`, «Тек_цена_ед» → `current_unit_price`. Avoid SQL reserved words as names (`order`, `user`, `group`, `position`, `value`): «Заказ» → `customer_order`, not `order`. Put the mapping «Сущность / атрибут на схеме → таблица / столбец» into the document (the entity list and attribute descriptions carry it), run the same pipeline, and say in the assumptions that the DDL and the English names were reconstructed.
  The pipeline needs concrete types, `NOT NULL`, keys and delete rules, but the source gives none of them — so every such choice is yours, and the document must not present it as fact. Mark each reconstructed value in the attribute table («`varchar(300)`, предположено») and turn the choices into open questions grouped by kind, one question each: types and lengths, which attributes are required, keys and uniqueness, delete behaviour, allowed values. A reader must be able to tell what came from the source and what was guessed.
- **The real database uses non-English identifiers.** The diagram shows identifiers as they are in the database; do not rename real objects silently. Mention it in «Объект описания» and, if the user asks, propose English names as a separate mapping table.
- **Updating an existing document.** Read the current version, parse the new DDL, find the difference (new or dropped tables, columns, links) and update only the affected sections, diagrams and the change history.
