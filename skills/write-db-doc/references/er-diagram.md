# ER diagram

The diagram is mandatory. Readers look at it first and only then go to the tables, so it must read without explanation: where the core of the model is, what depends on what, what is mandatory.

The diagram is drawn by `scripts/render_er.py` (SVG + PNG). PlantUML is not used: it cannot route lines at right angles and anchor them to PK/FK rows at the same time.

## Contents

1. Drawing rules
2. labels.json: entity names, link verbs, layout hints
3. Commands
4. Checking the result
5. Environment

## 1. Drawing rules

The renderer enforces these; do not work around them.

1. **Straight orthogonal lines.** A link consists only of horizontal and vertical segments. No diagonals, no curves.
2. **From the PK row to the FK row.** A link leaves the parent's primary-key row horizontally and enters the child's foreign-key row horizontally. This shows the link at the attribute level, which the document structure asks for.
3. **Parents left, children right.** Reference tables sit next to the tables that use them. A table referencing itself gets a loop on its less busy side.
4. **Own track per link.** Each link has its own vertical track in the gap between columns. Track order is chosen to minimise crossings. Where two different links meet at the same height, their corners are kept far apart so they do not read as one line.
5. **Shared PK row = shared line.** Several links leaving one PK row share the first segment, like a bus (as in a hand-drawn ER diagram), and split at their tracks. A bus carries one parent marker, so when the children differ in optionality (some FKs NOT NULL, some nullable) the row gets two parallel lines, `||` and `|o`, instead of one marker that would hide the difference.
6. **Logical links are dashed.** When two tables are linked by meaning but the database has no FK (`orders.customer_id` holds `customers.id` without a constraint), the link is drawn the same way — PK row to the column's row, orthogonal, with markers and a verb — but with a dashed line. The legend then gets a «логическая связь без FK» row. Solid line = FK in the database, dashed = the DBMS does not enforce it.
7. **Broken FKs are red.** A FK the DBMS will not create (incompatible types, target column without PK/UNIQUE, missing column — `critical` in model.json) is drawn red with a «FK не создастся» legend row, so the picture agrees with the «⛔ Критично» callout in the text.
8. **Crow's-foot notation.** Parent end: `||` exactly one (FK is NOT NULL), `|o` zero or one (FK nullable). Child end: `o{` zero or many, `o|` zero or one (FK is unique, a 1:1 link).
9. **Entity box: database identifiers only, in English.** A plain rectangle with square corners (no rounding). The header is the table name in upright bold (no italics), the rows are key (PK, FK, UQ) | column name | type | NOT NULL, exactly as in the database: `order`, `client_id`, `numeric(12,2)`. No Russian inside the boxes — Russian entity names live in the document text (the entity list maps «Заказ» ↔ `order`). PK columns are underlined; a required column has «NOT NULL» written in a fourth column (no bold for that). A legend in the bottom-right corner explains this.
10. **Verb labels in Russian.** A link may carry a Russian verb that reads from parent to child: «Клиент **формирует** заказ». Labels are placed beside their own line, off the markers, other lines and segments shared with other links, and inside the picture; where neighbouring lines leave no room, a label breaks its own line instead. The title and the legend are Russian too.
11. **Up to 15 entities per diagram.** For a larger schema draw an overview (`--keys-only`, only PK/FK rows) plus one diagram per subject area (`--tables`). Tables outside the selection that the selected ones reference are drawn as dashed stubs with their key only.

## 2. labels.json

```json
{
  "entities": {
    "crm.company": "Компания",
    "crm.deal": "Сделка",
    "deal_contact": "Участник сделки"
  },
  "links": {
    "deal.company_id": "заключает",
    "deal.owner_id": "ведёт",
    "crm.activity.deal_id": "содержит"
  },
  "logical": [
    {"child": "orders.customer_id", "parent": "customers.id", "label": "оформляет"},
    {"child": "category.parent_id", "parent": "category.id", "label": "включает"}
  ],
  "layout": {
    "column": {"segment": 0},
    "order": [["segment"], ["company", "employee"]]
  }
}
```

- `entities` — short Russian entity names, singular. They are **not drawn** (boxes show table names); keep them here so the entity list, the text and the link verbs use the same words. Keys are `schema.table` or `table`.
- `links` — key is `child_table.fk_column` (with or without schema) or the FK constraint name. The value is a verb in the present tense, third person, that completes «‹Родитель› … ‹потомок›»:
  - «Компания **имеет** контактных лиц», «Сотрудник **ведёт** сделки», «Сделка **содержит** активности», «Клиент **формирует** заказ», «Сотрудник **руководит** сотрудником».
  - Avoid empty verbs («связан», «относится») unless nothing better fits: they repeat what the line already says.
  - Use the same verb in the relationships table of the document («Смысл» column).
- `logical` (optional) — links without a FK, drawn dashed. `child` is `table.column` holding the reference, `parent` is `table.column` it points to (the column may be omitted for the PK). Add a link only when it is evident from names, types, comments or the user's words; `logical_link_candidates` in model.json lists columns that look like references — check each by meaning. A doubtful one is an open question, not a line.
- `layout` (optional) — pin a table to a column (`column`, 0 = leftmost) or set the top-to-bottom order of tables per column (`order`). Use it only when the automatic layout is clearly worse than what you need.

A flat `{"table": "Name"}` object is also accepted and treated as `entities`.

## 3. Commands

```bash
python3 "$SKILL_DIR/scripts/render_er.py" model.json -o er_full.svg --labels labels.json --title "<Система>: логическая структура БД"
```

Writes `er_full.svg` and `er_full.png` (2× scale). Big schema:

```bash
python3 "$SKILL_DIR/scripts/render_er.py" model.json -o er_overview.svg --keys-only --labels labels.json --title "Обзорная схема"
python3 "$SKILL_DIR/scripts/render_er.py" model.json -o er_sales.svg --tables deal,deal_contact,activity --labels labels.json --title "Продажи"
```

Options: `--max-columns N` keeps N non-key attributes per entity (PK/FK always stay; the rest collapse into «… ещё N»); `--no-types` hides types; `--no-stubs` hides referenced tables outside `--tables`; `--no-legend`.

The script prints the size and the number of track crossings: a few is normal, a big number means the layout needs a hint or a split.

## 4. Checking the result

Open the PNG with the image reader and check:
- every entity and every link is there; no line runs over a box or text;
- boxes contain only English database identifiers; labels, title and legend are Russian;
- each label sits next to its own line and does not cover a marker;
- no small «steps» where a line almost goes straight;
- text is readable at document width: the diagram is not wider than ~1800 px (at 1× scale, the SVG size). Wider means split by subject area.

If it looks wrong: split into subject areas; move a reference table with `layout.column`; reorder with `layout.order`; shorten wide tables with `--max-columns`. Then render again and look again.

## 5. Environment

- Python 3 standard library for the SVG.
- PNG needs `cairosvg` (`pip install --break-system-packages cairosvg`) or the `rsvg-convert` command. Without either you still get SVG: attach it and say PNG was not produced.
- Text widths are measured with Pillow and DejaVu Sans when available, otherwise estimated; the SVG asks for DejaVu Sans, Arial or Helvetica.
