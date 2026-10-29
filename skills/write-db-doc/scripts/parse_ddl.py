#!/usr/bin/env python3
"""Parse SQL DDL into a structured schema model (model.json).

Reads one or more DDL files (pg_dump --schema-only, migrations, hand-written scripts)
and saves tables, columns, keys, foreign keys, indexes, comments, enums, views and
critical problems and possible logical links as JSON. Optionally writes summary.md, a draft data dictionary in Russian
(the language of the final document).

Dependencies: Python 3.8+ standard library only.
PostgreSQL is the primary dialect; MySQL/MariaDB, MS SQL and generic SQL are handled for
CREATE TABLE / ALTER TABLE / CREATE INDEX / COMMENT. The dialect is detected from the text.

Usage:
    python3 parse_ddl.py schema.sql [more.sql ...] -o model.json [--summary summary.md]
    python3 parse_ddl.py migrations/ -o model.json      # every *.sql in the folder, by name

Migrations are applied in order (ALTER TABLE ADD/DROP/RENAME COLUMN, DROP TABLE),
so the model is the final state of the schema.

model.json: "critical" lists only problems that stop the schema from being created or a
table from working (worded in Russian, for «Критично» callouts in the document);
"logical_link_candidates" are columns that look like references but have no FK;
"warnings" are parser diagnostics for you.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Лексические утилиты
# ---------------------------------------------------------------------------

def split_statements(sql: str) -> list[str]:
    """Делит текст на операторы по ';' с учётом строк, $$-блоков и комментариев."""
    out, buf = [], []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        # однострочный комментарий
        if c == '-' and sql.startswith('--', i):
            j = sql.find('\n', i)
            i = n if j == -1 else j
            continue
        # блочный комментарий (без вложенности — достаточно для DDL)
        if c == '/' and sql.startswith('/*', i):
            j = sql.find('*/', i + 2)
            i = n if j == -1 else j + 2
            buf.append(' ')
            continue
        # строки в одинарных кавычках ('' внутри — экранирование)
        if c == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                if sql[j] == '\\' and j + 1 < n:  # E'..\'..' и MySQL
                    j += 2
                    continue
                j += 1
            buf.append(sql[i:j + 1])
            i = j + 1
            continue
        # идентификаторы в двойных кавычках / обратных апострофах / скобках MS SQL
        if c in '"`':
            j = sql.find(c, i + 1)
            j = n - 1 if j == -1 else j
            buf.append(sql[i:j + 1])
            i = j + 1
            continue
        # dollar-quoting PostgreSQL: $tag$ ... $tag$
        if c == '$':
            m = re.match(r'\$([A-Za-z_][A-Za-z0-9_]*)?\$', sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j == -1 else j + len(tag)
                buf.append(sql[i:j])
                i = j
                continue
        if c == ';':
            stmt = ''.join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = ''.join(buf).strip()
    if tail:
        out.append(tail)
    return out


def split_top(s: str, sep: str = ',') -> list[str]:
    """Делит строку по разделителю на верхнем уровне (вне скобок и кавычек)."""
    parts, depth, buf, i = [], 0, [], 0
    while i < len(s):
        c = s[i]
        if c in "'\"`":
            j = i + 1
            while j < len(s):
                if s[j] == c:
                    if c == "'" and j + 1 < len(s) and s[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            buf.append(s[i:j + 1])
            i = j + 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        if c == sep and depth == 0:
            parts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    if ''.join(buf).strip():
        parts.append(''.join(buf).strip())
    return parts


def match_paren(s: str, start: int) -> int:
    """Индекс закрывающей скобки для s[start] == '('."""
    depth, i = 0, start
    while i < len(s):
        c = s[i]
        if c in "'\"`":
            j = s.find(c, i + 1)
            while c == "'" and j != -1 and j + 1 < len(s) and s[j + 1] == "'":
                j = s.find(c, j + 2)
            i = len(s) if j == -1 else j + 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


IDENT = r'(?:"(?:[^"]|"")+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_\u0400-\u04FF][\w$\u0400-\u04FF]*)'
QNAME = rf'{IDENT}(?:\s*\.\s*{IDENT}){{0,2}}'


def unquote(ident: str) -> str:
    ident = ident.strip()
    if len(ident) >= 2 and ident[0] == ident[-1] == '"':
        return ident[1:-1].replace('""', '"')
    if len(ident) >= 2 and ident[0] == ident[-1] == '`':
        return ident[1:-1]
    if len(ident) >= 2 and ident[0] == '[' and ident[-1] == ']':
        return ident[1:-1]
    # PostgreSQL folds only ASCII letters of unquoted names: Клиент stays Клиент, Deal becomes deal
    return re.sub(r'[A-Z]+', lambda m: m.group(0).lower(), ident) if CASE_FOLD else ident


CASE_FOLD = True  # PostgreSQL приводит незакавыченные имена к нижнему регистру


def split_qname(q: str) -> list[str]:
    return [unquote(p) for p in re.findall(IDENT, q)]


def parse_qname(q: str) -> tuple[str | None, str]:
    parts = split_qname(q)
    if not parts:
        return None, q
    if len(parts) == 1:
        return None, parts[0]
    return parts[-2], parts[-1]


def ident_list(s: str) -> list[str]:
    """'(a, "B", c DESC)' -> ['a', 'B', 'c'] (выражения оставляем текстом)."""
    s = s.strip()
    if s.startswith('('):
        s = s[1:match_paren(s, 0)]
    cols = []
    for p in split_top(s):
        p = p.strip()
        m = re.match(rf'^({IDENT})(\s*\(\d+\))?(\s+(ASC|DESC|NULLS\s+\w+|\w+_ops|COLLATE\s+\S+))*\s*$', p, re.I)
        cols.append(unquote(m.group(1)) if m else p)
    return cols


def sql_string(s: str) -> str | None:
    s = s.strip()
    m = re.match(r"^[EN]?'(.*)'$", s, re.S | re.I)
    if not m:
        return None
    return m.group(1).replace("''", "'").replace("\\'", "'")


KW_COL_CONSTRAINT = (
    r'CONSTRAINT|NOT\s+NULL|NULL|DEFAULT|PRIMARY\s+KEY|UNIQUE|REFERENCES|CHECK|'
    r'GENERATED|COLLATE|AUTO_INCREMENT|AUTOINCREMENT|COMMENT|IDENTITY|ON\s+UPDATE|'
    r'CHARACTER\s+SET|CHARSET|UNSIGNED|ZEROFILL|SIGNED'
)


def find_top_kw(s: str, kw_regex: str, start: int = 0) -> re.Match | None:
    """Первое вхождение ключевого слова на верхнем уровне (вне скобок/кавычек)."""
    depth, i = 0, start
    rx = re.compile(rf'\b(?:{kw_regex})\b', re.I)
    while i < len(s):
        c = s[i]
        if c in "'\"`":
            j = s.find(c, i + 1)
            i = len(s) if j == -1 else j + 1
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif depth == 0 and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == '_')):
            m = rx.match(s, i)
            if m:
                return m
        i += 1
    return None


# ---------------------------------------------------------------------------
# Модель
# ---------------------------------------------------------------------------

class Schema:
    def __init__(self):
        self.tables: dict[str, dict] = {}
        self.enums: dict[str, dict] = {}
        self.domains: dict[str, dict] = {}
        self.views: dict[str, dict] = {}
        self.schemas: set[str] = set()
        self.sequences: set[str] = set()
        self.skipped: dict[str, int] = {}
        self.warnings: list[str] = []
        self.dialect = 'postgresql'

    # --- поиск таблицы по имени с учётом схемы ---
    def key(self, schema, name):
        return f'{schema}.{name}' if schema else name

    def find_table(self, schema, name):
        k = self.key(schema, name)
        if k in self.tables:
            return self.tables[k]
        # имя без схемы: public.x или единственная таблица с таким именем
        cand = [t for t in self.tables.values() if t['name'] == name and
                (schema is None or t['schema'] in (schema, None))]
        if schema is None:
            pub = [t for t in cand if t['schema'] in (None, 'public', 'dbo')]
            if len(pub) == 1:
                return pub[0]
        return cand[0] if len(cand) == 1 else None

    def new_table(self, schema, name):
        t = {
            'schema': schema, 'name': name, 'full_name': self.key(schema, name),
            'comment': None, 'columns': [], 'primary_key': [], 'unique': [],
            'foreign_keys': [], 'checks': [], 'indexes': [], 'partition_by': None,
            'partitions': [], 'inherits': [], 'kind': 'table',
        }
        self.tables[t['full_name']] = t
        return t

    @staticmethod
    def col(t, name):
        for c in t['columns']:
            if c['name'] == name:
                return c
        return None


def new_column(name, ctype):
    return {
        'name': name, 'type': ctype, 'nullable': True, 'default': None,
        'comment': None, 'pk': False, 'unique': False, 'fk': None,
        'identity': None, 'generated': None, 'checks': [],
    }


TYPE_SHORT = [
    (r'\bcharacter varying\b', 'varchar'), (r'\bcharacter\b(?! varying)', 'char'),
    (r'\btimestamp\s*(\(\d+\))?\s+without time zone\b', r'timestamp\1'),
    (r'\btimestamp\s*(\(\d+\))?\s+with time zone\b', r'timestamptz\1'),
    (r'\btime\s*(\(\d+\))?\s+without time zone\b', r'time\1'),
    (r'\btime\s*(\(\d+\))?\s+with time zone\b', r'timetz\1'),
    (r'\bdouble precision\b', 'float8'), (r'\bboolean\b', 'boolean'),
]


def short_type(t: str) -> str:
    t = re.sub(r'\s+', ' ', t.strip())
    t = re.sub(r'^(?:public|pg_catalog)\.', '', t)
    # INT, VARCHAR(255) -> int, varchar(255); значения ENUM('A','B') не трогаем
    q = t.find("'")
    t = (t[:q].lower() + t[q:]) if q != -1 else (t if '"' in t else t.lower())
    for rx, rep in TYPE_SHORT:
        t = re.sub(rx, rep, t, flags=re.I)
    return t


# ---------------------------------------------------------------------------
# Разбор элементов
# ---------------------------------------------------------------------------

FK_ACTION = r'(?:CASCADE|RESTRICT|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT)(?:\s*\([^)]*\))?'


def parse_references(s: str) -> dict | None:
    m = re.match(rf'\s*REFERENCES\s+({QNAME})\s*(\([^)]*\))?(.*)$', s, re.I | re.S)
    if not m:
        return None
    rs, rn = parse_qname(m.group(1))
    rest = m.group(3) or ''
    od = re.search(rf'ON\s+DELETE\s+({FK_ACTION})', rest, re.I)
    ou = re.search(rf'ON\s+UPDATE\s+({FK_ACTION})', rest, re.I)
    return {
        'ref_schema': rs, 'ref_table': rn,
        'ref_columns': ident_list(m.group(2)) if m.group(2) else [],
        'on_delete': re.sub(r'\s+', ' ', od.group(1).upper()) if od else None,
        'on_update': re.sub(r'\s+', ' ', ou.group(1).upper()) if ou else None,
        'deferrable': bool(re.search(r'\bDEFERRABLE\b', rest, re.I)
                           and not re.search(r'NOT\s+DEFERRABLE', rest, re.I)),
    }


def parse_table_constraint(item: str) -> dict | None:
    """PRIMARY KEY / UNIQUE / FOREIGN KEY / CHECK / EXCLUDE / MySQL KEY|INDEX."""
    s = item.strip()
    name = None
    m = re.match(rf'CONSTRAINT\s+({IDENT})\s+(.*)$', s, re.I | re.S)
    if m:
        name, s = unquote(m.group(1)), m.group(2).strip()
    def paren_group(pos):
        p0 = s.find('(', pos)
        p1 = match_paren(s, p0) if p0 != -1 else -1
        return s[p0:p1 + 1] if p1 != -1 else None

    m = re.match(r'PRIMARY\s+KEY\s*(?:CLUSTERED|NONCLUSTERED)?\s*(?=\()', s, re.I)
    if m:
        return {'kind': 'pk', 'name': name, 'columns': ident_list(paren_group(m.end()))}
    m = re.match(rf'UNIQUE\s*(?:NULLS\s+(?:NOT\s+)?DISTINCT\s*)?(?:CLUSTERED\s*|NONCLUSTERED\s*)?(?:(?:KEY|INDEX)\s*)?({IDENT})?\s*(?=\()', s, re.I)
    if m:
        return {'kind': 'unique', 'name': name or (unquote(m.group(1)) if m.group(1) else None),
                'columns': ident_list(paren_group(m.end()))}
    m = re.match(rf'FOREIGN\s+KEY\s*({IDENT})?\s*(\([^)]*\))\s*(REFERENCES.*)$', s, re.I | re.S)
    if m:
        ref = parse_references(m.group(3)) or {}
        return {'kind': 'fk', 'name': name, 'columns': ident_list(m.group(2)), **ref}
    m = re.match(r'CHECK\s*(\(.*\))\s*(NOT\s+VALID)?', s, re.I | re.S)
    if m:
        expr = m.group(1)
        return {'kind': 'check', 'name': name, 'expr': expr[1:match_paren(expr, 0)].strip()}
    if re.match(r'EXCLUDE\b', s, re.I):
        return {'kind': 'exclude', 'name': name, 'expr': s}
    m = re.match(rf'(?:(FULLTEXT|SPATIAL)\s+)?(?:KEY|INDEX)\s*({IDENT})?\s*(?=\()', s, re.I)
    if m:
        return {'kind': 'index', 'name': unquote(m.group(2)) if m.group(2) else None,
                'columns': ident_list(paren_group(m.end())), 'method': (m.group(1) or '').lower() or None}
    return None


def parse_column(item: str) -> tuple[dict, list[dict]]:
    """Определение столбца -> (column, [inline constraints as table constraints])."""
    m = re.match(rf'\s*({IDENT})\s*(.*)$', item, re.S)
    name, rest = unquote(m.group(1)), m.group(2).strip()
    km = find_top_kw(rest, KW_COL_CONSTRAINT)
    ctype = rest[:km.start()].strip() if km else rest
    cons = rest[km.start():] if km else ''
    col = new_column(name, short_type(ctype))
    extra = []
    low = ctype.lower()
    if re.match(r'(small|big)?serial\d?\b', low):
        col['identity'] = 'serial'
        col['nullable'] = False
    # последовательно разбираем ограничения столбца
    pos = 0
    while cons and pos < len(cons):
        sub = cons[pos:]
        m = re.match(rf'\s*CONSTRAINT\s+({IDENT})', sub, re.I)
        if m:
            pos += m.end()
            continue
        m = re.match(r'\s*NOT\s+NULL\b', sub, re.I)
        if m:
            col['nullable'] = False; pos += m.end(); continue
        m = re.match(r'\s*NULL\b', sub, re.I)
        if m:
            pos += m.end(); continue
        m = re.match(r'\s*PRIMARY\s+KEY\b(\s*(ASC|DESC|CLUSTERED|NONCLUSTERED))?', sub, re.I)
        if m:
            col['pk'] = True; col['nullable'] = False; pos += m.end(); continue
        m = re.match(r'\s*UNIQUE\b(\s+KEY)?', sub, re.I)
        if m:
            col['unique'] = True; pos += m.end(); continue
        m = re.match(r'\s*(AUTO_INCREMENT|AUTOINCREMENT)\b', sub, re.I)
        if m:
            col['identity'] = 'auto_increment'; pos += m.end(); continue
        m = re.match(r'\s*IDENTITY\s*(\([^)]*\))?', sub, re.I)
        if m:
            col['identity'] = 'identity'; col['nullable'] = False; pos += m.end(); continue
        m = re.match(r'\s*GENERATED\s+(ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY\s*(\([^)]*\))?', sub, re.I)
        if m:
            col['identity'] = 'identity'; col['nullable'] = False; pos += m.end(); continue
        m = re.match(r'\s*(?:GENERATED\s+ALWAYS\s+)?AS\s*\(', sub, re.I)
        if m:
            p0 = pos + m.end() - 1
            p1 = match_paren(cons, p0)
            col['generated'] = cons[p0 + 1:p1].strip()
            pos = p1 + 1
            m2 = re.match(r'\s*(STORED|VIRTUAL|PERSISTENT)\b', cons[pos:], re.I)
            if m2:
                pos += m2.end()
            continue
        m = re.match(r'\s*CHECK\s*\(', sub, re.I)
        if m:
            p0 = pos + m.end() - 1
            p1 = match_paren(cons, p0)
            col['checks'].append(cons[p0 + 1:p1].strip())
            pos = p1 + 1
            continue
        m = re.match(r'\s*REFERENCES\b', sub, re.I)
        if m:
            nxt = find_top_kw(sub[m.end():], r'NOT\s+NULL|NULL|DEFAULT|PRIMARY\s+KEY|UNIQUE|CHECK|COLLATE|COMMENT|CONSTRAINT')
            end = m.end() + nxt.start() if nxt else len(sub)
            ref = parse_references(sub[:end])
            if ref:
                extra.append({'kind': 'fk', 'name': None, 'columns': [name], **ref})
            pos += end
            continue
        m = re.match(r'\s*DEFAULT\s+', sub, re.I)
        if m:
            nxt = find_top_kw(sub[m.end():], r'NOT\s+NULL|NULL|PRIMARY\s+KEY|UNIQUE|CHECK|REFERENCES|COLLATE|COMMENT|CONSTRAINT|GENERATED|ON\s+UPDATE|AUTO_INCREMENT')
            end = m.end() + nxt.start() if nxt else len(sub)
            col['default'] = sub[m.end():end].strip()
            pos += end
            continue
        m = re.match(r"\s*COMMENT\s+('(?:[^']|'')*')", sub, re.I)
        if m:
            col['comment'] = sql_string(m.group(1)); pos += m.end(); continue
        m = re.match(rf'\s*COLLATE\s+({IDENT}|\S+)', sub, re.I)
        if m:
            pos += m.end(); continue
        m = re.match(r'\s*(CHARACTER\s+SET|CHARSET)\s+\S+', sub, re.I)
        if m:
            pos += m.end(); continue
        m = re.match(r'\s*ON\s+UPDATE\s+(\S+(\(\))?)', sub, re.I)
        if m:
            col['on_update'] = m.group(1); pos += m.end(); continue
        m = re.match(r'\s*(UNSIGNED|SIGNED|ZEROFILL)\b', sub, re.I)
        if m:
            col['type'] += ' ' + m.group(1).lower(); pos += m.end(); continue
        # неизвестный хвост — сохраняем, чтобы не потерять
        col.setdefault('unparsed', sub.strip())
        break
    em = re.match(r"(enum|set)\s*\((.*)\)\s*$", col['type'], re.I | re.S)
    if em:  # MySQL ENUM('a','b') прямо в типе столбца
        col['enum_values'] = [sql_string(v) for v in split_top(em.group(2)) if v.strip()]
    if col['identity'] == 'auto_increment' and col['default'] is None:
        col['default'] = 'AUTO_INCREMENT'
    if col['default'] and re.match(r"nextval\(", col['default'], re.I):
        col['identity'] = col['identity'] or 'sequence'
    return col, extra


def apply_constraint(sch: Schema, t: dict, c: dict):
    k = c['kind']
    if k == 'pk':
        t['primary_key'] = c['columns']
        t['pk_name'] = c.get('name')
        for cn in c['columns']:
            col = sch.col(t, cn)
            if col:
                col['pk'] = True
                col['nullable'] = False
    elif k == 'unique':
        t['unique'].append({'name': c.get('name'), 'columns': c['columns']})
        if len(c['columns']) == 1:
            col = sch.col(t, c['columns'][0])
            if col:
                col['unique'] = True
    elif k == 'fk':
        fk = {key: c.get(key) for key in ('name', 'columns', 'ref_schema', 'ref_table',
                                           'ref_columns', 'on_delete', 'on_update', 'deferrable')}
        t['foreign_keys'].append(fk)
    elif k == 'check':
        t['checks'].append({'name': c.get('name'), 'expr': c['expr']})
    elif k == 'exclude':
        t['checks'].append({'name': c.get('name'), 'expr': c['expr'], 'exclude': True})
    elif k == 'index':
        t['indexes'].append({'name': c.get('name'), 'columns': c['columns'], 'unique': False,
                             'method': c.get('method'), 'where': None, 'include': []})


def parse_bounds(text: str) -> dict:
    """FOR VALUES FROM (..) TO (..) | IN (..) | WITH (..) | DEFAULT -> dict."""
    if re.search(r'\bDEFAULT\b', text, re.I) and not re.search(r'FOR\s+VALUES', text, re.I):
        return {'default': True}
    m = re.search(r"FOR\s+VALUES\s+FROM\s*\((.*?)\)\s*TO\s*\((.*?)\)", text, re.I | re.S)
    if m:
        return {'from': m.group(1).strip(), 'to': m.group(2).strip()}
    m = re.search(r"FOR\s+VALUES\s+IN\s*\((.*?)\)", text, re.I | re.S)
    if m:
        return {'in': m.group(1).strip()}
    m = re.search(r"FOR\s+VALUES\s+WITH\s*\((.*?)\)", text, re.I | re.S)
    if m:
        return {'hash': m.group(1).strip()}
    return {}


def parse_create_table(sch: Schema, stmt: str):
    m = re.match(
        rf'CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:GLOBAL|LOCAL)\s+)?(?:TEMP(?:ORARY)?\s+|UNLOGGED\s+)?'
        rf'TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?({QNAME})\s*(.*)$', stmt, re.I | re.S)
    if not m:
        return
    schema, name = parse_qname(m.group(1))
    rest = m.group(2)
    if re.match(r'PARTITION\s+OF\b', rest, re.I):
        pm = re.match(rf'PARTITION\s+OF\s+({QNAME})', rest, re.I)
        ps, pn = parse_qname(pm.group(1))
        parent = sch.find_table(ps, pn)
        if parent is not None:
            parent['partitions'].append(sch.key(schema, name))
            parent.setdefault('partition_bounds', {})[sch.key(schema, name)] = parse_bounds(rest)
        else:
            sch.warnings.append(f'Partition {sch.key(schema, name)} refers to unknown table {pn}')
        return
    if re.match(r'AS\b', rest, re.I) or not rest.startswith('('):
        sch.skipped['CREATE TABLE AS / no column list'] = sch.skipped.get('CREATE TABLE AS / no column list', 0) + 1
        return
    end = match_paren(rest, 0)
    body, tail = rest[1:end], rest[end + 1:]
    if schema:
        sch.schemas.add(schema)
    key = sch.key(schema, name)
    if key in sch.tables:
        sch.warnings.append(f'Table {key} is declared twice; the last definition is used')
        del sch.tables[key]
    t = sch.new_table(schema, name)
    deferred = []
    for item in split_top(body):
        if not item:
            continue
        if re.match(r'(CONSTRAINT|PRIMARY\s+KEY|UNIQUE\s*(KEY|INDEX)?\s*[\w"`]*\s*\(|FOREIGN\s+KEY|CHECK\s*\(|EXCLUDE|'
                    r'(FULLTEXT\s+|SPATIAL\s+)?(KEY|INDEX)\s+[\w"`]*\s*\()', item, re.I):
            c = parse_table_constraint(item)
            if c:
                deferred.append(c)
            else:
                sch.warnings.append(f'{key}: constraint not parsed: "{item[:80]}"')
            continue
        if re.match(r'LIKE\s', item, re.I):
            sch.warnings.append(f'{key}: LIKE {item[5:].strip()[:60]} is used; its columns are not expanded')
            continue
        col, extra = parse_column(item)
        t['columns'].append(col)
        deferred.extend(extra)
        if col['pk']:
            t['primary_key'] = t['primary_key'] or [col['name']]
    for c in deferred:
        apply_constraint(sch, t, c)
    pm = re.search(r'PARTITION\s+BY\s+(\w+)\s*\(([^)]*)\)', tail, re.I)
    if pm:
        t['partition_by'] = f'{pm.group(1).upper()} ({pm.group(2).strip()})'
    im = re.search(r'INHERITS\s*\(([^)]*)\)', tail, re.I)
    if im:
        t['inherits'] = [sch.key(*parse_qname(x)) for x in split_top(im.group(1))]
    cm = re.search(r"COMMENT\s*=?\s*('(?:[^']|'')*')", tail, re.I)
    if cm:
        t['comment'] = sql_string(cm.group(1))


def parse_alter_table(sch: Schema, stmt: str):
    m = re.match(rf'ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?({QNAME})\s+(.*)$', stmt, re.I | re.S)
    if not m:
        return
    schema, name = parse_qname(m.group(1))
    t = sch.find_table(schema, name)
    actions = split_top(m.group(2))
    for a in actions:
        a = a.strip()
        if re.match(r'(OWNER\s+TO|SET\s+\(|SET\s+SCHEMA|ENABLE|DISABLE|REPLICA|CLUSTER|SET\s+(LOGGED|UNLOGGED|WITH|WITHOUT|TABLESPACE|ACCESS))', a, re.I):
            continue
        if t is None:
            sch.warnings.append(f'ALTER TABLE {name}: table not found, skipped "{a[:60]}"')
            continue
        mm = re.match(r'ADD\s+(?!COLUMN\b)(CONSTRAINT\s+.*|PRIMARY\s+KEY.*|UNIQUE.*|FOREIGN\s+KEY.*|CHECK.*|EXCLUDE.*)$', a, re.I | re.S)
        if mm:
            c = parse_table_constraint(mm.group(1))
            if c:
                apply_constraint(sch, t, c)
            else:
                sch.warnings.append(f'{t["full_name"]}: not parsed: "{a[:80]}"')
            continue
        mm = re.match(r'ADD\s+(?:COLUMN\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(.*)$', a, re.I | re.S)
        if mm:
            col, extra = parse_column(mm.group(1))
            old = sch.col(t, col['name'])
            if old:
                t['columns'].remove(old)
            t['columns'].append(col)
            for c in extra:
                apply_constraint(sch, t, c)
            if col['pk']:
                apply_constraint(sch, t, {'kind': 'pk', 'name': None, 'columns': [col['name']]})
            continue
        mm = re.match(rf'DROP\s+(?:COLUMN\s+)?(?:IF\s+EXISTS\s+)?({IDENT})', a, re.I)
        if mm and not re.match(r'DROP\s+(CONSTRAINT|DEFAULT|NOT\s+NULL)', a, re.I):
            cn = unquote(mm.group(1))
            t['columns'] = [c for c in t['columns'] if c['name'] != cn]
            t['foreign_keys'] = [f for f in t['foreign_keys'] if cn not in f['columns']]
            continue
        mm = re.match(rf'DROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?({IDENT})', a, re.I)
        if mm:
            cn = unquote(mm.group(1))
            t['foreign_keys'] = [f for f in t['foreign_keys'] if f.get('name') != cn]
            t['unique'] = [u for u in t['unique'] if u.get('name') != cn]
            t['checks'] = [c for c in t['checks'] if c.get('name') != cn]
            if t.get('pk_name') == cn:
                for c in t['columns']:
                    c['pk'] = False
                t['primary_key'] = []
            continue
        mm = re.match(rf'RENAME\s+(?:COLUMN\s+)?({IDENT})\s+TO\s+({IDENT})', a, re.I)
        if mm and not re.match(r'RENAME\s+(TO|CONSTRAINT)\b', a, re.I):
            col = sch.col(t, unquote(mm.group(1)))
            if col:
                col['name'] = unquote(mm.group(2))
            continue
        mm = re.match(rf'ALTER\s+(?:COLUMN\s+)?({IDENT})\s+(.*)$', a, re.I | re.S)
        if mm:
            col = sch.col(t, unquote(mm.group(1)))
            op = mm.group(2).strip()
            if col is None:
                continue
            if re.match(r'SET\s+DEFAULT\s+', op, re.I):
                col['default'] = re.sub(r'^SET\s+DEFAULT\s+', '', op, flags=re.I).strip()
                if re.match(r'nextval\(', col['default'], re.I):
                    col['identity'] = col['identity'] or 'sequence'
            elif re.match(r'DROP\s+DEFAULT', op, re.I):
                col['default'] = None
            elif re.match(r'SET\s+NOT\s+NULL', op, re.I):
                col['nullable'] = False
            elif re.match(r'DROP\s+NOT\s+NULL', op, re.I):
                col['nullable'] = True
            elif re.match(r'ADD\s+GENERATED', op, re.I):
                col['identity'] = 'identity'
                col['nullable'] = False
            elif re.match(r'(SET\s+DATA\s+)?TYPE\s+', op, re.I):
                col['type'] = short_type(re.sub(r'^(SET\s+DATA\s+)?TYPE\s+', '', op, flags=re.I).split(' USING ')[0])
            continue
        mm = re.match(rf'RENAME\s+TO\s+({IDENT})', a, re.I)
        if mm:
            new = unquote(mm.group(1))
            del sch.tables[t['full_name']]
            t['name'] = new
            t['full_name'] = sch.key(t['schema'], new)
            sch.tables[t['full_name']] = t
            continue
        if re.match(r'ATTACH\s+PARTITION\s', a, re.I):
            pm = re.match(rf'ATTACH\s+PARTITION\s+({QNAME})', a, re.I)
            part = sch.find_table(*parse_qname(pm.group(1)))
            if part is not None:
                part['kind'] = 'partition'
                t['partitions'].append(part['full_name'])
                t.setdefault('partition_bounds', {})[part['full_name']] = parse_bounds(a)
            continue
        sch.warnings.append(f'{t["full_name"]}: ALTER TABLE action not parsed: "{a[:80]}"')


def parse_create_index(sch: Schema, stmt: str):
    m = re.match(
        rf'CREATE\s+(UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?'
        rf'({QNAME})?\s*ON\s+(?:ONLY\s+)?({QNAME})\s*(?:USING\s+(\w+)\s*)?(\(.*)$', stmt, re.I | re.S)
    if not m:
        sch.warnings.append(f'Index not parsed: "{stmt[:80]}"')
        return
    t = sch.find_table(*parse_qname(m.group(3)))
    if t is None:
        return
    body = m.group(5)
    end = match_paren(body, 0)
    tail = body[end + 1:]
    inc = re.search(r'INCLUDE\s*(\([^)]*\))', tail, re.I)
    wh = re.search(r'WHERE\s+(.*)$', tail, re.I | re.S)
    t['indexes'].append({
        'name': parse_qname(m.group(2))[1] if m.group(2) else None,
        'columns': ident_list(body[:end + 1]),
        'unique': bool(m.group(1)),
        'method': (m.group(4) or 'btree').lower(),
        'where': wh.group(1).strip() if wh else None,
        'include': ident_list(inc.group(1)) if inc else [],
    })
    if m.group(1) and not (wh) and len(ident_list(body[:end + 1])) == 1:
        col = sch.col(t, ident_list(body[:end + 1])[0])
        if col:
            col['unique'] = True


def parse_comment(sch: Schema, stmt: str):
    m = re.match(rf"COMMENT\s+ON\s+(TABLE|COLUMN|VIEW|MATERIALIZED\s+VIEW|TYPE|DOMAIN|SCHEMA)\s+({QNAME})\s+IS\s+(.*)$",
                 stmt, re.I | re.S)
    if not m:
        return
    kind = re.sub(r'\s+', ' ', m.group(1).upper())
    text = sql_string(m.group(3).strip())
    parts = split_qname(m.group(2))
    if kind == 'COLUMN':
        if len(parts) < 2:
            return
        cn, tn = parts[-1], parts[-2]
        ts = parts[-3] if len(parts) >= 3 else None
        t = sch.find_table(ts, tn)
        if t is None:
            v = sch.views.get(sch.key(ts, tn)) or next((x for x in sch.views.values() if x['name'] == tn), None)
            if v is not None:
                v.setdefault('column_comments', {})[cn] = text
            return
        col = sch.col(t, cn)
        if col is not None:
            col['comment'] = text
    elif kind == 'TABLE':
        s, n = (parts[-2] if len(parts) > 1 else None), parts[-1]
        t = sch.find_table(s, n)
        if t is not None:
            t['comment'] = text
    elif kind in ('VIEW', 'MATERIALIZED VIEW'):
        n = parts[-1]
        v = next((x for x in sch.views.values() if x['name'] == n), None)
        if v is not None:
            v['comment'] = text
    elif kind in ('TYPE', 'DOMAIN'):
        n = parts[-1]
        for coll in (sch.enums, sch.domains):
            for e in coll.values():
                if e['name'] == n:
                    e['comment'] = text


def parse_statement(sch: Schema, stmt: str):
    s = stmt.strip()
    head = s[:60].upper()
    head = re.sub(r'\s+', ' ', head)
    if re.match(r'CREATE (OR REPLACE )?((GLOBAL|LOCAL) )?(TEMP(ORARY)? |UNLOGGED )?TABLE', head):
        parse_create_table(sch, s)
    elif head.startswith('ALTER TABLE'):
        parse_alter_table(sch, s)
    elif re.match(r'CREATE (UNIQUE )?((NON)?CLUSTERED )?INDEX', head):
        parse_create_index(sch, s)
    elif head.startswith('COMMENT ON'):
        parse_comment(sch, s)
    elif re.match(r'CREATE TYPE', head):
        m = re.match(rf"CREATE\s+TYPE\s+({QNAME})\s+AS\s+ENUM\s*\((.*)\)\s*$", s, re.I | re.S)
        if m:
            es, en = parse_qname(m.group(1))
            vals = [sql_string(v) for v in split_top(m.group(2)) if v.strip()]
            sch.enums[sch.key(es, en)] = {'schema': es, 'name': en, 'values': vals, 'comment': None}
        else:
            sch.skipped['CREATE TYPE (not ENUM)'] = sch.skipped.get('CREATE TYPE (not ENUM)', 0) + 1
    elif re.match(r'CREATE DOMAIN', head):
        m = re.match(rf'CREATE\s+DOMAIN\s+({QNAME})\s+(?:AS\s+)?(.*)$', s, re.I | re.S)
        if m:
            ds, dn = parse_qname(m.group(1))
            body = m.group(2)
            km = find_top_kw(body, r'NOT\s+NULL|NULL|DEFAULT|CHECK|CONSTRAINT|COLLATE')
            sch.domains[sch.key(ds, dn)] = {'schema': ds, 'name': dn,
                                            'type': short_type(body[:km.start()] if km else body),
                                            'definition': body.strip(), 'comment': None}
    elif re.match(r'CREATE (OR REPLACE )?(MATERIALIZED )?VIEW', head):
        m = re.match(rf'CREATE\s+(?:OR\s+REPLACE\s+)?(MATERIALIZED\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?({QNAME})(.*?)\bAS\b(.*)$',
                     s, re.I | re.S)
        if m:
            vs, vn = parse_qname(m.group(2))
            sch.views[sch.key(vs, vn)] = {'schema': vs, 'name': vn, 'materialized': bool(m.group(1)),
                                          'definition': m.group(4).strip(), 'comment': None}
    elif re.match(r'CREATE SCHEMA', head):
        m = re.match(rf'CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?({IDENT})', s, re.I)
        if m:
            sch.schemas.add(unquote(m.group(1)))
    elif re.match(r'CREATE SEQUENCE', head):
        m = re.match(rf'CREATE\s+SEQUENCE\s+(?:IF\s+NOT\s+EXISTS\s+)?({QNAME})', s, re.I)
        if m:
            sch.sequences.add(sch.key(*parse_qname(m.group(1))))
    elif re.match(r'DROP TABLE', head):
        m = re.match(rf'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(.*?)(\s+CASCADE|\s+RESTRICT)?\s*$', s, re.I | re.S)
        for q in split_top(m.group(1)) if m else []:
            t = sch.find_table(*parse_qname(q))
            if t is not None:
                del sch.tables[t['full_name']]
    else:
        # name the object, so the reader can find it in the DDL: triggers and functions
        # often hold business rules that the document must describe in words
        m = re.match(r'\s*(CREATE|ALTER|DROP|COMMENT|GRANT|REVOKE|SET|SELECT|INSERT|DO)\b'
                     r'(?:\s+OR\s+REPLACE)?(?:\s+(?:CONSTRAINT|EVENT|MATERIALIZED|UNIQUE|TEMP|TEMPORARY))?'
                     r'\s*(\w+)?\s*(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([\w."`\[\]$]+)?', s, re.I)
        if m and m.group(2):
            word = ' '.join(x for x in (m.group(1).upper(), m.group(2).upper(), m.group(3)) if x)
        else:
            word = ' '.join(head.split()[:2]) if head else '?'
        sch.skipped[word] = sch.skipped.get(word, 0) + 1


# ---------------------------------------------------------------------------
# Пост-обработка и замечания
# ---------------------------------------------------------------------------

TYPE_GROUPS = [
    ('int', r'^(small|big|tiny|medium)?int\w*|^integer|^(small|big)?serial|^int[248]|^numeric|^decimal|^number'),
    ('text', r'^(text|varchar|character|char|bpchar|citext|nvarchar|nchar|string|clob)'),
    ('uuid', r'^uuid|^uniqueidentifier'),
    ('time', r'^(date|time|timestamp|datetime)'),
    ('bool', r'^(bool|bit)'),
    ('binary', r'^(bytea|blob|binary|varbinary)'),
]


def type_group(t):
    t = (t or '').lower().strip()
    for g, rx in TYPE_GROUPS:
        if re.match(rx, t):
            return g
    return None


def find_critical(sch, tables):
    """Only problems that stop the schema from being created or a table from working.
    Worded in Russian: they go into the document as «Критично» callouts."""
    out = []
    import datetime
    today = datetime.date.today()
    for t in tables:
        fn = t['full_name']
        for fk in t['foreign_keys']:
            cols = ', '.join(fk['columns'])
            target = sch.tables.get(fk.get('ref_full_name'))
            if fk.get('ref_missing') or target is None:
                out.append({'table': fn, 'type': 'fk_missing_table', 'columns': fk['columns'],
                            'text': f'внешний ключ ({cols}) ссылается на таблицу {fk["ref_table"]}, которой нет в DDL; '
                                    f'если её нет и в БД, таблица {t["name"]} не создастся'})
                continue
            for rc in fk['ref_columns']:
                if sch.col(target, rc) is None:
                    out.append({'table': fn, 'type': 'fk_missing_column', 'columns': fk['columns'],
                                'text': f'внешний ключ ({cols}) ссылается на столбец {target["name"]}.{rc}, которого нет; '
                                        f'таблица {t["name"]} не создастся'})
            uniq = [target['primary_key']] + [u['columns'] for u in target['unique']] + \
                   [i['columns'] for i in target['indexes'] if i['unique'] and not i.get('where')]
            if fk['ref_columns'] and not any(u and set(u) == set(fk['ref_columns']) for u in uniq):
                out.append({'table': fn, 'type': 'fk_target_not_unique', 'columns': fk['columns'],
                            'text': f'внешний ключ ({cols}) ссылается на {target["name"]}({", ".join(fk["ref_columns"])}), '
                                    f'где нет первичного ключа или уникального ограничения; СУБД не создаст такой ключ'})
            for c, rc in zip(fk['columns'], fk['ref_columns']):
                a, b = sch.col(t, c), sch.col(target, rc)
                if a and b:
                    ga, gb = type_group(a['type']), type_group(b['type'])
                    if ga and gb and ga != gb:
                        out.append({'table': fn, 'type': 'fk_type_mismatch', 'columns': [c],
                                    'text': f'тип {t["name"]}.{c} ({a["type"]}) несовместим с {target["name"]}.{rc} '
                                            f'({b["type"]}); внешний ключ не создастся'})
        for c in t['columns']:
            e = next((x for x in sch.enums.values() if x['name'] == c.get('enum')), None)
            if e and c.get('default'):
                m = re.match(r"\s*'((?:[^']|'')*)'", c['default'])
                if m and m.group(1).replace("''", "'") not in e['values']:
                    out.append({'table': fn, 'type': 'enum_default_invalid', 'columns': [c['name']],
                                'text': f'значение по умолчанию {c["default"]} для {c["name"]} не входит в перечисление '
                                        f'{e["name"]}; PostgreSQL проверяет значение по умолчанию при создании, таблица {t["name"]} не создастся'})
        if t.get('partition_by'):
            bounds = t.get('partition_bounds', {})
            if not t['partitions']:
                out.append({'table': fn, 'type': 'no_partitions',
                            'text': f'таблица {t["name"]} секционирована ({t["partition_by"]}), но секций нет; '
                                    f'любая вставка завершится ошибкой'})
            elif not any(b.get('default') for b in bounds.values()) and t['partition_by'].startswith('RANGE'):
                ends = []
                for b in bounds.values():
                    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", b.get('to', ''))
                    if m:
                        ends.append(datetime.date(*map(int, m.groups())))
                starts = []
                for b in bounds.values():
                    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", b.get('from', ''))
                    if m:
                        starts.append(datetime.date(*map(int, m.groups())))
                if ends:
                    last = max(ends)
                    if last <= today:
                        out.append({'table': fn, 'type': 'partition_expired',
                                    'text': f'последняя секция {t["name"]} заканчивается {last:%d.%m.%Y}, секции DEFAULT нет; '
                                            f'вставка строк с текущими датами уже завершается ошибкой'})
                    elif (last - today).days <= 180:
                        out.append({'table': fn, 'type': 'partition_ending',
                                    'text': f'последняя секция {t["name"]} заканчивается {last:%d.%m.%Y}, секции DEFAULT нет; '
                                            f'с этой даты вставка строк будет завершаться ошибкой'})
                    if starts and min(starts) > today:
                        out.append({'table': fn, 'type': 'partition_future',
                                    'text': f'секции {t["name"]} начинаются с {min(starts):%d.%m.%Y}; '
                                            f'строки с текущими датами вставить нельзя'})
    return out


def find_logical_links(tables):
    """Columns that look like references but have no FK: name and type match another table's key.
    These are hints: confirm them by meaning before drawing them as logical (dashed) links."""
    by_name = {}
    for t in tables:
        by_name.setdefault(t['name'].lower(), t)
        n = t['name'].lower()
        for alias in (n[:-1] if n.endswith('s') else None, n[:-2] if n.endswith('es') else None,
                      n[:-3] + 'y' if n.endswith('ies') else None):
            if alias:
                by_name.setdefault(alias, t)
    pk_cols = {}
    for t in tables:
        if len(t['primary_key']) == 1:
            pk_cols.setdefault(t['primary_key'][0].lower(), []).append(t)
    out = []
    for t in tables:
        fk_cols = {c for fk in t['foreign_keys'] for c in fk['columns']}
        for c in t['columns']:
            if c['name'] in fk_cols or (c['pk'] and len(t['primary_key']) == 1):
                continue
            name = c['name'].lower()
            hit, reason = None, None
            m = re.match(r'^(.+?)_(id|code|uuid|key|no|num|login|sku)$', name) or re.match(r'^id_(.+)$', name)
            if m:
                stem = m.group(1)
                target = by_name.get(stem)
                if target is None and stem in ('parent', 'manager', 'owner_parent') and len(t['primary_key']) == 1:
                    target = t
                if target is not None and len(target['primary_key']) == 1:
                    hit, reason = target, f'имя {c["name"]} указывает на таблицу {target["name"]}'
            if hit is None and name in pk_cols:
                cands = [x for x in pk_cols[name] if x is not t]
                if len(cands) == 1 and name != 'id':
                    hit, reason = cands[0], f'имя совпадает с первичным ключом {cands[0]["name"]}.{c["name"]}'
            if hit is None:
                continue
            pk = hit['primary_key'][0]
            pcol = next((x for x in hit['columns'] if x['name'] == pk), None)
            if pcol and type_group(pcol['type']) and type_group(c['type']) and \
                    type_group(pcol['type']) != type_group(c['type']):
                continue
            out.append({'child': t['full_name'], 'column': c['name'], 'parent': hit['full_name'],
                        'parent_column': pk, 'reason': reason})
    return out


def finalize(sch: Schema) -> dict:
    # связываем FK со столбцами и целевыми таблицами
    for t in sch.tables.values():
        for fk in t['foreign_keys']:
            target = sch.find_table(fk['ref_schema'], fk['ref_table'])
            if target is None:
                fk['ref_full_name'] = sch.key(fk['ref_schema'], fk['ref_table'])
                fk['ref_missing'] = True
                sch.warnings.append(f'{t["full_name"]}: foreign key to table {fk["ref_table"]} that is not in the DDL')
            else:
                fk['ref_full_name'] = target['full_name']
                fk['ref_missing'] = False
                if not fk['ref_columns']:
                    fk['ref_columns'] = list(target['primary_key'])
            for cn in fk['columns']:
                col = sch.col(t, cn)
                if col is not None:
                    col['fk'] = {'table': fk['ref_full_name'],
                                 'column': fk['ref_columns'][fk['columns'].index(cn)]
                                 if len(fk['ref_columns']) == len(fk['columns']) else None}
        # перечисления и домены, на которые ссылаются столбцы
        for c in t['columns']:
            base = re.sub(r'\[\]$', '', c['type']).split('.')[-1].strip('"')
            for e in sch.enums.values():
                if e['name'] == base:
                    c['enum'] = e['name']
            for d in sch.domains.values():
                if d['name'] == base:
                    c['domain'] = d['name']
    # секции — отдельный вид, чтобы не путать с самостоятельными таблицами
    for t in sch.tables.values():
        for p in t['partitions']:
            if p in sch.tables:
                sch.tables[p]['kind'] = 'partition'

    tables = [t for t in sch.tables.values() if t['kind'] == 'table']
    critical = find_critical(sch, tables)
    candidates = find_logical_links(tables)
    # классификация таблиц: справочник / связующая / основная
    referenced = {}
    for t in tables:
        for fk in t['foreign_keys']:
            referenced[fk['ref_full_name']] = referenced.get(fk['ref_full_name'], 0) + 1
    for t in tables:
        fk_cols = {c for fk in t['foreign_keys'] for c in fk['columns']}
        non_meta = [c for c in t['columns'] if not re.match(r'(created|updated|deleted)_(at|by|on)$', c['name'])]
        if t['primary_key'] and set(t['primary_key']) <= fk_cols and len(t['foreign_keys']) >= 2:
            t['role_hint'] = 'связующая (M:N)'
        elif len(t['foreign_keys']) >= 2 and len(non_meta) - len(fk_cols) <= 2:
            t['role_hint'] = 'связующая (M:N)'
        elif (not t['foreign_keys'] and referenced.get(t['full_name'])
              and len([c for c in non_meta if not c['pk']]) <= 3
              and any(re.search(r'(name|title|caption|label|descr)', c['name'], re.I) for c in t['columns'])):
            t['role_hint'] = 'справочник'
        else:
            t['role_hint'] = 'основная'
        t['referenced_by'] = sorted({o['full_name'] for o in tables for fk in o['foreign_keys']
                                     if fk['ref_full_name'] == t['full_name']})

    return {
        'dialect': sch.dialect,
        'schemas': sorted(sch.schemas),
        'tables': list(sch.tables.values()),
        'enums': list(sch.enums.values()),
        'domains': list(sch.domains.values()),
        'views': list(sch.views.values()),
        'sequences': sorted(sch.sequences),
        'critical': critical,
        'logical_link_candidates': candidates,
        'warnings': sch.warnings,
        'skipped_statements': sch.skipped,
        'stats': {
            'tables': len(tables),
            'partitions': sum(1 for t in sch.tables.values() if t['kind'] == 'partition'),
            'columns': sum(len(t['columns']) for t in tables),
            'foreign_keys': sum(len(t['foreign_keys']) for t in tables),
            'enums': len(sch.enums), 'views': len(sch.views),
        },
    }


# ---------------------------------------------------------------------------
# Краткая сводка в Markdown — черновик словаря данных для автора документа
# ---------------------------------------------------------------------------

def md_escape(s):
    return (s or '').replace('|', '\\|').replace('\n', ' ')


def summary_md(model: dict) -> str:
    L = ['# Сводка по схеме', '']
    st = model['stats']
    L.append(f"Таблиц: {st['tables']}, столбцов: {st['columns']}, внешних ключей: {st['foreign_keys']}, "
             f"перечислений: {st['enums']}, представлений: {st['views']}.")
    L.append('')
    for t in model['tables']:
        if t['kind'] != 'table':
            continue
        L.append(f"## {t['full_name']} — {t.get('role_hint', '')}")
        if t['comment']:
            L.append(f"Комментарий: {t['comment']}")
        if t['partition_by']:
            L.append(f"Секционирование: {t['partition_by']}, секций: {len(t['partitions'])}")
        L.append('')
        L.append('| Столбец | Тип | Обяз. | Ключ | По умолчанию | Комментарий |')
        L.append('|---|---|---|---|---|---|')
        for c in t['columns']:
            keys = []
            if c['pk']:
                keys.append('PK')
            if c['fk']:
                keys.append(f"FK → {c['fk']['table']}.{c['fk']['column'] or '?'}")
            if c['unique'] and not c['pk']:
                keys.append('UQ')
            dflt = c['default'] or ''
            if c['identity']:
                dflt = f"{c['identity']}" + (f" ({dflt})" if dflt and c['identity'] != 'auto_increment' else '')
            L.append(f"| {c['name']} | {md_escape(c['type'])} | {'нет' if c['nullable'] else 'да'} | "
                     f"{', '.join(keys)} | {md_escape(dflt)} | {md_escape(c['comment'])} |")
        if t['checks']:
            L.append('')
            L.append('Проверки: ' + '; '.join(f"`{md_escape(c['expr'])}`" for c in t['checks']))
        if t['unique']:
            L.append('Уникальность: ' + '; '.join('(' + ', '.join(u['columns']) + ')' for u in t['unique']))
        if t['indexes']:
            L.append('Индексы: ' + '; '.join(
                f"{i['name'] or '—'} ({', '.join(i['columns'])}){' UNIQUE' if i['unique'] else ''}"
                f"{' ' + i['method'] if i['method'] and i['method'] != 'btree' else ''}"
                f"{' WHERE ' + i['where'] if i['where'] else ''}" for i in t['indexes']))
        for fk in t['foreign_keys']:
            L.append(f"Связь: ({', '.join(fk['columns'])}) → {fk['ref_full_name']} ({', '.join(fk['ref_columns'])})"
                     f"{' ON DELETE ' + fk['on_delete'] if fk['on_delete'] else ''}"
                     f"{' ON UPDATE ' + fk['on_update'] if fk['on_update'] else ''}")
        L.append('')
    if model['enums']:
        L.append('## Перечисления')
        for e in model['enums']:
            L.append(f"- {e['name']}: {', '.join(e['values'])}" + (f" — {e['comment']}" if e['comment'] else ''))
        L.append('')
    if model['views']:
        L.append('## Представления')
        for v in model['views']:
            L.append(f"- {v['name']}{' (materialized)' if v['materialized'] else ''}"
                     + (f" — {v['comment']}" if v['comment'] else ''))
        L.append('')
    if model['critical']:
        L.append('## Критичные проблемы (схема не создастся или таблица перестанет работать)')
        for i in model['critical']:
            L.append(f"- {i['table']}: {i['text']}")
        L.append('')
    if model['logical_link_candidates']:
        L.append('## Возможные логические связи без FK (проверить по смыслу)')
        for c in model['logical_link_candidates']:
            L.append(f"- {c['child']}.{c['column']} → {c['parent']}.{c['parent_column']}: {c['reason']}")
        L.append('')
    if model['warnings']:
        L.append('## Предупреждения разбора')
        for w in model['warnings']:
            L.append(f'- {w}')
    return '\n'.join(L) + '\n'


def collect_files(paths: list[str]) -> list[Path]:
    files = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            files.extend(sorted(pp.rglob('*.sql')))
        else:
            files.append(pp)
    return files


def main():
    global CASE_FOLD
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inputs', nargs='+', help='.sql files or migration folders')
    ap.add_argument('-o', '--output', default='model.json')
    ap.add_argument('--summary', help='also write a draft data dictionary (Russian Markdown)')
    ap.add_argument('--dialect', choices=['postgresql', 'mysql', 'mssql', 'generic'],
                    help='SQL dialect; detected from the text by default')
    ap.add_argument('--keep-case', action='store_true',
                    help='do not lower-case unquoted names (default for MySQL and MS SQL)')
    args = ap.parse_args()
    CASE_FOLD = not args.keep_case

    sch = Schema()
    files = collect_files(args.inputs)
    if not files:
        sys.exit('No .sql files found')
    texts = [f.read_text(encoding='utf-8', errors='replace') for f in files]
    allsql = '\n'.join(texts)
    if args.dialect:
        sch.dialect = args.dialect
    elif re.search(r'`|\bENGINE\s*=|\bAUTO_INCREMENT\b', allsql, re.I):
        sch.dialect = 'mysql'
    elif re.search(r'^\s*GO\s*$|\[\w+\]\.\[|\bIDENTITY\s*\(\s*\d+\s*,|\bNVARCHAR\b', allsql, re.I | re.M):
        sch.dialect = 'mssql'
    if sch.dialect in ('mysql', 'mssql') and not args.keep_case:
        CASE_FOLD = False
    for f, text in zip(files, texts):
        # мета-команды psql (\connect, \restrict) и разделители GO (MS SQL)
        text = re.sub(r'^\s*\\.*$', '', text, flags=re.M)
        text = re.sub(r'^\s*GO\s*$', ';', text, flags=re.M | re.I)
        for stmt in split_statements(text):
            try:
                parse_statement(sch, stmt)
            except Exception as e:  # не роняем весь разбор из-за одного оператора
                sch.warnings.append(f'{f.name}: failed to parse "{stmt[:60]}": {e}')
    model = finalize(sch)
    model['sources'] = [str(f) for f in files]
    Path(args.output).write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.summary:
        Path(args.summary).write_text(summary_md(model), encoding='utf-8')
    st = model['stats']
    print(f"Done: {args.output} ({model['dialect']}). Tables {st['tables']}, columns {st['columns']}, "
          f"foreign keys {st['foreign_keys']}, enums {st['enums']}, views {st['views']}.")
    print(f"Critical problems: {len(model['critical'])}, possible logical links: "
          f"{len(model['logical_link_candidates'])}, parser warnings: {len(model['warnings'])}.")
    if model['warnings']:
        for w in model['warnings'][:10]:
            print('  !', w)


if __name__ == '__main__':
    main()
