# Writing style

The document is written in **Russian**. These guidelines are in English; every example of wording is in Russian, because that is what goes into the document.

The readers are developers, testers, analysts from other teams and DBAs. Each comes with a question: where is X stored, what does this field mean, what happens if I delete this row. The text is good if the answer is found within a minute and understood one way only.

The style rests on two books:

- **«Пиши, сокращай»** (М. Ильяхов, Л. Сарычева) — information style: usefulness to the reader, facts instead of evaluations, honesty, no verbal clutter.
- **«Python. К вершинам мастерства»** (Л. Рамальо, *Fluent Python*) — how to explain a complex system: every decision has a reason, every concept has an example, terms are precise and consistent, pitfalls are named openly.

What follows applies these principles to database documentation. It is a distillation, not a summary of the books.

## 1. Information style («Пиши, сокращай»)

### More use, fewer words

Every sentence answers a reader's question or goes. Test: if the sentence is removed, does the reader lose anything? If not, remove it.

| Instead of | Write |
|---|---|
| Данная таблица предназначена для осуществления хранения информации о сделках. | Одна строка — одна сделка с компанией. |
| Поле является идентификатором записи. | Суррогатный ключ, значение выдаёт СУБД (identity). |
| В случае удаления компании производится каскадное удаление контактов. | При удалении компании СУБД удаляет её контакты (ON DELETE CASCADE). |
| Поле содержит информацию о дате закрытия сделки. | Дата закрытия; заполняется при переходе в `won` или `lost`. |

### Facts instead of evaluations

An evaluation («быстрый», «удобный», «надёжный», «эффективный», «оптимальный») tells the reader nothing they can check. Replace it with a fact: a number, a mechanism, a consequence.

- Not: «Индекс обеспечивает быстрый поиск сделок.»
- But: «Индекс `deal_open_idx` по (owner_id, stage) с условием `closed_at IS NULL` покрывает экран «Мои открытые сделки»: СУБД читает только открытые сделки менеджера.»

### Stop words

Words that hurt more often than help. When you meet one, reread the phrase. `scripts/lint_style.py` finds most of them.

- **Канцелярит**: является, осуществляет, данный, в рамках, в целях, в случае, посредством, соответствующий. «Является» is almost always a dash: «Сделка — договорённость с компанией о продаже».
- **Verbal nouns**: «осуществление хранения», «проведение проверки». Bring the verb back: «хранит», «проверяет».
- **Impersonal passive**: «данные формируются», «проверка выполняется». Name the actor: «СУБД проверяет», «триггер записывает», «сервис заказов создаёт». («Хранится» describing storage is fine: «сумма хранится в копейках».)
- **Fillers and intensifiers**: очень, достаточно, как правило, по сути, фактически, безусловно. Delete without loss.
- **Vagueness**: некоторые, различные, определённый, и т. д., и др. Be concrete: «этапы `lead`, `qualified`, `proposal`».
- **Clichés**: играет важную роль, широкий спектр, позволяет обеспечить. Say plainly what and why.

Exceptions are terms. «Данные», «информационное обеспечение», «уникальный ключ», «обязательный атрибут», «многие ко многим» are concepts of the domain and of the standard, not clutter.

### Honesty

Do not hide how the schema actually behaves behind smooth wording: if a status is free text without a check, write «Допустимые значения СУБД не проверяет»; if a delete cascades, say what disappears. State it as a fact, without advice. If the meaning of a field is unknown, do not invent it: move it to «Открытые вопросы».

| Invented (bad) | Honest (good) |
|---|---|
| `position` — порядковый номер автора на обложке. | `position` — порядковый номер автора в книге, по умолчанию 1 (по имени поля; уточнить, вопрос 6). |
| Сегменты: SMB, Enterprise, Госсектор. | Состав сегментов в DDL не задан (вопрос 2). |

### Readability

- One thought per sentence; up to 20–25 words.
- A paragraph is 1–4 sentences.
- A list when items are of one kind and there are three or more.
- A table when items share the same set of properties (attributes, links, indexes).
- Main point first: the purpose of an entity in the first sentence, details after.

### Editing

Write fully first, then cut. Three passes: remove stop words; replace evaluations with facts; split long sentences. Then run `$SKILL_DIR/scripts/lint_style.py`.

## 2. Way of explaining (Ramalho)

### Explain why, not only what

The DDL already says *what*. The document is worth reading for what the DDL does not say: why it is built this way and what follows from it.

- «Этап сделки — перечисление `deal_stage`, а не справочная таблица: набор этапов фиксирован и меняется только вместе с кодом воронки.»
- «Ключ `activity` составной (`id`, `happened_at`): так требует секционирование по дате — PostgreSQL проверяет уникальность только внутри секции.»

If the reason is unknown, do not make it up. State the fact and ask the question.

### Concept → example

After describing an entity or a link, where it helps, show a short example: a typical SQL query, a sample row, a scenario. The example must run on the described schema: take table and column names from `model.json`.

```sql
-- Открытые сделки менеджера: использует индекс deal_open_idx
SELECT id, company_id, stage, amount
FROM crm.deal
WHERE owner_id = :employee_id AND closed_at IS NULL;
```

Not every entity needs one — only where it is not obvious how to use the data: link tables, life cycles, partitioning, soft delete, hierarchies.

### Precise and consistent terms

One concept, one word throughout the document. Once it is «Компания», do not switch to «клиент», «организация», «контрагент». Define terms in «Термины и сокращения» and stick to them. The same Russian entity names go into `labels.json`, so the diagram and the text agree. Database object names are in monospace: `crm.deal.amount`.

### Callouts for what matters

Mark pitfalls with callouts so nobody misses them:

> **Внимание.** Удаление сделки каскадно удаляет её активности и участников. Для отказа от сделки используйте этап `lost`, а не DELETE.

> **Примечание.** `closed_at` хранится без часового пояса, в отличие от `created_at`. Сравнивайте их с осторожностью.

> **Совет.** Ищите сотрудника по почте через `lower(email) = lower(:email)`: только такое условие использует индекс `employee_email_uidx`.

Three kinds for facts about behaviour: **Примечание** — a useful detail; **Внимание** — data can be lost or corrupted by normal use (cascade delete); **Совет** — how to query or use the schema more easily (not how to change it). A fourth, **⛔ Критично**, is reserved for a problem that breaks a table (see `gost-structure.md`).

### Facts, not opinions

The document records the schema as it is. Recommendations («добавить индекс», «переименовать поле», «заменить CASCADE на RESTRICT») do not belong here — schema review is a separate task. The one exception, «⛔ Критично», is defined in `gost-structure.md`; stylistically it follows the same rule as everything else here: fact and effect, no advice.

## 3. Ready-made Russian phrasings

Use these patterns; adapt the words, keep the shape.

| Situation | Pattern |
|---|---|
| Purpose of an entity | «Одна строка — одно(а) ‹объект›.» / «Одна строка — участие ‹A› в ‹B›.» |
| Who creates rows | «Строку создаёт ‹сервис/роль› при ‹событии›.» |
| Surrogate key | «Суррогатный ключ, значение выдаёт СУБД (identity).» |
| Natural key | «Естественный ключ: `inn` — две компании с одним ИНН завести нельзя.» |
| FK attribute | «Компания, с которой заключается сделка.» (the noun, not «ссылка на …») |
| Default value | «По умолчанию `now()` — момент вставки строки.» |
| Allowed values | «Одно из: `lead`, `qualified`, `proposal`, `won`, `lost` (п. 3.5).» |
| Not checked by DB | «Формат СУБД не проверяет.» |
| Logical link | «Ссылка на `customers.id`; внешнего ключа нет, СУБД связь не контролирует.» |
| Critical | «> **⛔ Критично.** ‹факт›: ‹что перестанет работать›.» |
| Unknown meaning | «… (по имени поля; уточнить, вопрос 4).» |
| Delete behaviour | «При удалении ‹родителя› СУБД удаляет ‹потомков› (CASCADE).» / «Удалить ‹родителя› с ‹потомками› нельзя (NO ACTION).» |
| Section intro | «Раздел описывает состав данных, их форматы и взаимосвязи.» (no reference to the standard) |
| Open question | «4. `employee.is_active`: что делает приложение с неактивным сотрудником — скрывает из списков, передаёт его сделки другому?» |
