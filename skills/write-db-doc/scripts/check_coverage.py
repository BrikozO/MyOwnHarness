#!/usr/bin/env python3
"""Check a draft document against model.json: is everything described, is nothing invented.

Checks:
  1. every table of the model is mentioned in the document;
  2. the subsection of each entity (a heading that contains the table name) lists all its columns;
  3. `table.column` and `schema.table.column` references in prose exist in the model;
  4. no attribute row has an empty description;
  5. the document embeds an ER diagram (an image link to *.png / *.svg or blob/<id>);
  6. the document does not cite standards (ГОСТ, РД 50-34, clause numbers like «п. 8.9»):
     the structure follows GOST, the text never names it. --allow-standard-refs turns this
     off when the user explicitly asked for references.

Usage:
    python3 check_coverage.py model.json draft.md [--allow-standard-refs]
Exit code 0 - nothing to fix, 1 - see the list.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    allow_refs = '--allow-standard-refs' in sys.argv[1:]
    if len(args) != 2:
        sys.exit(__doc__)
    model = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    doc = Path(args[1]).read_text(encoding='utf-8')
    tables = [t for t in model['tables'] if t.get('kind', 'table') == 'table']
    problems = []

    # sections by markdown headings
    heads = [(m.start(), len(m.group(1)), m.group(2)) for m in re.finditer(r'^(#{1,6})\s+(.*)$', doc, re.M)]

    def section_for(t):
        # 'crm.deal', 'таблица deal', 'Сделка (`deal`)' all count as the entity heading
        pat = re.compile(rf'(?<![\w]){re.escape(t["name"])}(?![\w])', re.I)
        for i, (pos, lvl, title) in enumerate(heads):
            if pat.search(title.replace('`', '')):
                end = next((p for p, l, _ in heads[i + 1:] if l <= lvl), len(doc))
                return doc[pos:end]
        return None

    for t in tables:
        if not re.search(rf'(?<![\w]){re.escape(t["name"])}(?![\w])', doc):
            problems.append(f'Table {t["full_name"]} is not mentioned in the document')
            continue
        sec = section_for(t)
        if sec is None:
            problems.append(f'No subsection for {t["full_name"]} (put the table name in its heading)')
            continue
        missing = [c['name'] for c in t['columns']
                   if not re.search(rf'(?<![\w]){re.escape(c["name"])}(?![\w])', sec)]
        if missing:
            problems.append(f'{t["full_name"]}: columns missing from its subsection: {", ".join(missing)}')
        # a column listed with an empty description is the schema printed again, not documented
        names = {c['name'].lower() for c in t['columns']}
        empty = []
        for line in sec.splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')] if line.lstrip().startswith('|') else []
            if len(cells) >= 3 and cells[0].strip('`').lower() in names and not cells[-1].strip(' -—–'):
                empty.append(cells[0].strip('`'))
        if empty:
            problems.append(f'{t["full_name"]}: empty description for: {", ".join(empty)}')

    # references to non-existent columns (outside code blocks)
    prose = re.sub(r'```.*?```', ' ', doc, flags=re.S)
    cols = {}
    for t in tables:
        for key in {t['name'], t['full_name']}:
            cols[key.lower()] = {c['name'].lower() for c in t['columns']}
    known_schemas = {s.lower() for s in model.get('schemas', [])}
    for m in re.finditer(r'`([\w$]+(?:\.[\w$]+){1,2})`', prose):
        parts = m.group(1).lower().split('.')
        if len(parts) == 3:
            tkey, col = f'{parts[0]}.{parts[1]}', parts[2]
        elif parts[0] in known_schemas:
            continue  # schema.table: checked above
        else:
            tkey, col = parts[0], parts[1]
        if tkey in cols and col not in cols[tkey]:
            problems.append(f'Reference `{m.group(1)}`: no such column in the model')
        elif tkey not in cols and len(parts) == 3:
            problems.append(f'Reference `{m.group(1)}`: no such table in the model')

    if not re.search(r'!\[[^\]]*\]\([^)]*(?:\.(?:png|svg)|blob/[^)]*)\)|<svg\b|<img\b', doc, re.I):
        problems.append('No ER diagram image in the document (expected ![Рисунок N — ...](er.png) or a blob link)')

    if not allow_refs:
        prose = re.sub(r'```.*?```', ' ', doc, flags=re.S)
        # «п. 3.3.1» pointing to the document's own section is fine; a clause number that is
        # not a section of this document («п. 8.9») is a reference to the standard
        own = {m.group(1) for m in re.finditer(r'^#{1,6}\s+(\d+(?:\.\d+)*)\b', doc, re.M)}
        refs = re.compile(r'ГОСТ|GOST|РД\s*50-34|\bп\.\s*(\d+\.\d+(?:\.\d+)*)', re.I)
        for ln, line in enumerate(prose.splitlines(), 1):
            for m in refs.finditer(line):
                if m.group(1) and m.group(1) in own:
                    continue
                problems.append(f'line {ln}: reference to a standard «{line.strip()[:70]}» — '
                                'the document follows GOST without naming it')
                break

    if problems:
        print(f'Problems: {len(problems)}')
        for p in problems:
            print(' -', p)
        sys.exit(1)
    print(f'Full coverage: {len(tables)} tables, {sum(len(t["columns"]) for t in tables)} columns.')


if __name__ == '__main__':
    main()
