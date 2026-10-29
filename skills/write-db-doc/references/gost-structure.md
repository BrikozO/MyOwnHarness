# Document structure and the GOST anchor

The document is written in Russian. Section headings, table captions and sample sentences below are given in Russian exactly as they should appear; explanations are in English.

## Contents

1. Standards that apply
2. What ГОСТ Р 59795-2021 requires for database documents
3. Main template: «Описание базы данных»
4. Variant: «Описание организации информационной базы»
5. Variant: only the «Логическая структура» section
6. Formatting

## 1. Standards that apply

- **ГОСТ Р 59795-2021** «Автоматизированные системы. Требования к содержанию документов» — replaced РД 50-34.698-90. Section 8 covers documents on information support. The main anchor of this skill. Never cite РД 50-34.698-90 as current.
- **ГОСТ 34.201-2020** — kinds and completeness of documents for an automated system.
- **ГОСТ 34.602-2020** — technical specification (ТЗ); its requirements on information support are worth checking against the database description.
- **ГОСТ 2.105** — general requirements for text documents (numbering, tables, figures). Applied lightly.

The standards are voluntary unless a contract or ТЗ requires them. The document follows the standards without mentioning them: no standard names, no clause numbers («п. 8.9»), no «согласно ГОСТ», no remarks like «сверьте с официальным текстом ГОСТ». The structure itself is the anchor. Everything in this file about clauses is for you, to choose and fill sections — never text for the document. References go in only if the user explicitly asks for them; notes about the standard, if any, go to the chat reply.

## 2. What ГОСТ Р 59795-2021 requires

**п. 8.9 «Описание базы данных»** — closest to a logical schema:
- the list of domain objects whose information the database holds;
- the list of entities and their attributes with the main characteristics of the attributes;
- the links between entities at the attribute level.

**п. 8.5 «Описание организации информационной базы»**:
- in-machine information base («внутримашинная информационная база»):
  - logical structure — composition of the data, formats and interrelations (8.5.2.1);
  - physical structure — physical implementation of the databases and data arrays (8.5.2.2);
  - lists of databases and arrays and the logical links between them (8.5.2.3);
  - maintenance — procedures to create, update and service the base, schedule, protection against destruction and unauthorised access, relation to input data (8.5.2.4);
- off-machine information base («внемашинная информационная база») — documents and messages and the system functions that produce or use them (8.5.3).

**п. 8.3 «Описание информационного обеспечения системы»** — one level up: composition and organisation of information support, classifiers, data exchange with other systems. The skill does not write it, but its in-machine part can be taken from the database description.

**п. 8.6 «Описание систем классификации и кодирования»** — per classifier: what it classifies, coding method, code structure and length, source (ОКВЭД, ОКСМ, in-house). If the schema has such reference tables, describe them briefly in «Справочники и перечисления» and refer to this document.

**п. 8.7 «Описание массива информации»** — for file arrays outside the database. Usually not needed.

## 3. Main template: «Описание базы данных»

Write this document by default. Sections 1–3 and 6 are mandatory. Sections 4–5 hold what is known: facts from the DDL and the user, then a line «Остальное неизвестно — см. вопросы N–M» for the gaps. Only when nothing at all is known, keep the heading and write «Сведений нет — см. открытые вопросы».

```
<Наименование системы>. Описание базы данных <имя БД>
Версия 0.1 · <ДД.ММ.ГГГГ> · Черновик · Источник: <файл DDL / коммит>

История изменений  (таблица: Версия | Дата | Автор | Что изменено; Автор — кто готовит документ, если пользователь это сказал, иначе «—»)
Допущения          (список; только если что-то пришлось предположить)

1 Общие сведения
  1.1 Назначение документа
  1.2 Объект описания
  1.3 Термины и сокращения
  1.4 Связанные документы              [only if the user gave project documents]

2 Объекты предметной области

3 Логическая структура
  3.1 ER-диаграмма
  3.2 Перечень сущностей
  3.3 Описание сущностей
      3.3.1 <Сущность> (`<table>`)
      ...
  3.4 Связи между сущностями
  3.5 Справочники и перечисления

4 Физическая структура
5 Организация ведения базы данных
6 Открытые вопросы
```

Where the sections come from (for you; none of this goes into the document): 2 and 3.2–3.4 — п. 8.9 (domain objects, entities and attributes, links at the attribute level); 3 as a whole — п. 8.5.2.1; 3.5 — п. 8.6 for classifiers; 4 — п. 8.5.2.2; 5 — п. 8.5.2.4.

The document records the schema as it is. It is not a review: no section of remarks, no improvement proposals («добавить индекс», «заменить на RESTRICT»). Schema review is a separate task for a separate skill. The only exception is **critical problems** — see «Критично» callouts below.

### 1 Общие сведения

**1.1 Назначение документа.** One or two sentences: what it describes and who needs it. «Документ описывает логическую и физическую структуру БД CRM. Нужен разработчикам и тестировщикам сервисов продаж, аналитикам отчётности и DBA.»

**1.2 Объект описания.** A list: DBMS and version; database name and schemas; source of the description (file, export date, migration commit); size — tables, attributes, links (from `stats` in model.json). Unknown DBMS version → open question.

**1.3 Термины и сокращения.** Table «Термин | Определение». Only what the document uses: domain terms (Сделка, Воронка) and technical ones (PK, FK, UQ, NOT NULL, identity, секция). One sentence per definition.

**1.4 Связанные документы.** Only real project documents the user gave or named: ТЗ, «Описание информационного обеспечения», «Описание систем классификации и кодирования», API specs. Never list GOST standards here, never mention the input DDL or picture (that is already in 1.2 «Объект описания»), never add a remark about checking against the standard. Nothing to list — leave the subsection out.

### 2 Объекты предметной области

Table «Подобласть | Объект предметной области | Что это | Сущности». An object is a business concept, not a table: «Сделка», «Клиент», «Сотрудник отдела продаж». One object may map to several tables («Сделка» → `deal`, `deal_contact`, `activity`). The subject areas («Клиенты», «Продажи», «Справочники») later define how diagrams are split.

### 3 Логическая структура

**3.1 ER-диаграмма.** Mandatory. Embed the PNG, caption below: «Рисунок 1 — ER-диаграмма схемы `crm` (логическая структура)». Then one or two sentences on how to read it:

> Как читать: родители слева, потомки справа. Линия выходит из строки первичного ключа родителя и входит в строку внешнего ключа потомка; подпись на линии читается от родителя к потомку. Ядро модели — `deal`. Обозначения концов линий — в легенде.

Up to 15 entities — one detailed diagram. More — an overview plus one diagram per subject area, each with its own figure number. Rules: `er-diagram.md`.

**3.2 Перечень сущностей.** Table «№ | Сущность | Таблица | Вид | Назначение». Kind: «основная», «справочник», «связующая (M:N)», «журнал» (history, audit, events). `role_hint` in model.json is a hint; check it against the meaning. Purpose — one phrase.

**3.3 Описание сущностей.** One subsection per entity; the table name must be in the heading (the coverage check looks for it):

```
3.3.N <Сущность> (таблица `<table>`)

<First sentence: what one row is.> «Одна строка — одна сделка с компанией.»
<Who creates and changes rows and when, if known.>
Ключ: `<pk>`; естественный ключ: `<uq>` (если есть).

Таблица N — Атрибуты сущности «<Сущность>»
| Атрибут | Тип | Обяз. | Ключ | Описание |

Ограничения и правила: <CHECK, uniqueness, triggers, rules from comments — as a list>.
Жизненный цикл: <for a status/stage — values and transitions>.
Пример: <SQL or scenario — only where it helps>.
Callouts «Внимание» / «Примечание» / «Совет» — facts about behaviour; «Критично» — only for a problem that breaks the table.
```

Attribute table columns:
- **Атрибут** — column name in monospace: `amount`.
- **Тип** — as in the database, short: `numeric(14,2)`, `varchar(12)`, `timestamptz`; for an enum, the type name.
- **Обяз.** — «да» for NOT NULL, otherwise «нет».
- **Ключ** — PK, FK, UQ; for FK, the target: «FK → `company.id`».
- **Описание** — meaning, units, format, allowed values, default and who sets it. Start with a noun: «Сумма сделки в валюте `currency`, не меньше 0». Never «Поле содержит…».

Take descriptions from database comments (`COMMENT ON`), names, constraints and what the user said. What none of these give, do not invent: write the obvious from the name and add «(по имени поля; уточнить, вопрос N)».

**3.4 Связи между сущностями.** The standard asks for links at the attribute level. Caption «Таблица N — Связи между сущностями»:

| № | Родитель (атрибут) | Потомок (атрибут) | Кардинальность | Обязательность | При удалении / изменении | Смысл |
|---|---|---|---|---|---|---|
| 1 | `company.id` | `deal.company_id` | 1 : 0..N | обязательна | запрещено (NO ACTION) | Компания заключает сделки |

- Кардинальность: «1 : 0..N»; «1 : 0..1» (FK is unique); «M : N» — through a link entity, name it.
- Обязательность: FK NOT NULL — «обязательна», otherwise «необязательна».
- При удалении / изменении: ON DELETE / ON UPDATE; nothing declared → «запрещено (NO ACTION)».
- Смысл — a business phrase with the same verb as on the diagram: «Сотрудник ведёт сделки».

**Logical links** — the data is linked by meaning but there is no FK in the database (`orders.customer_id` holds `customers.id`, no constraint). They go into the same table, marked in «При удалении / изменении» as «логическая связь, СУБД не контролирует», and onto the diagram as dashed lines (`logical` in labels.json). Include a logical link only when it is evident: name and type match a key, a comment or the user says so. Candidates from `logical_link_candidates` in model.json are hints, not facts; a doubtful one becomes an open question, not a line.

After the table, list the cascade chains: «`deal` → `activity`, `deal_contact`».

**3.5 Справочники и перечисления.** For enums (ENUM, CHECK IN (...)) — table «Значение | Смысл». For reference tables — purpose, who maintains them, where values come from. External classifiers — refer to «Описание систем классификации и кодирования».

### 4 Физическая структура

Short and factual, from the DDL: DBMS and version; schemas; key generation (identity, sequence, auto_increment); partitioning (key, partitions, default partition); indexes — table «Таблица | Индекс | Поля | Вид | Зачем» (btree, unique, partial, functional, covering, gin); views, functions, triggers — name and purpose.

### 5 Организация ведения базы данных

Only from the user or the DDL: how the schema is created and changed (migration tool), which services write which tables, backups, roles and grants. Nothing known — say so and move questions to section 6.

### «Критично» callouts

Only for a problem because of which the schema will not be created or a table will stop working: a FK to a table or column that does not exist, a FK to columns without PK/UNIQUE, incompatible FK types, an enum default outside the enum, a partitioned table without a partition for current (or soon) dates and without DEFAULT. The parser lists them in `critical` in model.json; add one yourself only if it is equally certain. Put the callout inline, in the subsection of the affected entity (or in 4 for partitions), in this exact form:

> **⛔ Критично.** Последняя секция `activity` заканчивается 01.01.2027, секции DEFAULT нет: с этой даты вставка активностей будет завершаться ошибкой.

State the fact and the effect, nothing else — no proposal, no fix. Everything that is merely suboptimal (missing index, nullable FK, no comments in the database, cascade delete, odd naming) is **not** critical: describe it as plain fact where it belongs («Индекса по `activity.deal_id` нет», «При удалении сделки СУБД удаляет её активности (CASCADE)») or leave it out.

### 6 Открытые вопросы

A numbered list. Each question is concrete, with options when there are any: «3. `deal.currency`: какие валюты допустимы? В БД нет проверки, по умолчанию `RUB`.» Attribute descriptions refer to them: «уточнить, вопрос 3».

## 4. Variant: «Описание организации информационной базы»

When this document is asked for (п. 8.5), regroup the same material:

```
1 Описание внутримашинной информационной базы
  1.1 Логическая структура        ← sections 2 and 3 of the main template
  1.2 Физическая структура        ← section 4
  1.3 Организация ведения         ← section 5
2 Описание внемашинной информационной базы
  ← documents and messages the system receives or issues; nothing known → a question
Открытые вопросы — as in the main template
```

## 5. Variant: only «Логическая структура»

For a section that goes into another document (технический проект, a wiki page of the system): section 3 of the template in full, a one-sentence intro on what the section describes, objects of the domain as 1.1, then open questions. Number from what the user says, otherwise from 1.

## 6. Formatting

- Sections numbered with Arabic numerals: 1, 1.1, 1.1.1.
- Tables: caption above, «Таблица N — Название», numbered through the document.
- Figures: caption below, «Рисунок N — Название», numbered through the document.
- Database object names in monospace.
- Dates ДД.ММ.ГГГГ; numbers with a space between thousands (10 000).
- No «мы», «вы» in the text; questions in «Открытые вопросы» may address the reader.
