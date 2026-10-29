#!/usr/bin/env python3
"""Regression tests for the skill's scripts (standard library only).

    python3 tests/test_scripts.py          # from the skill folder

The render tests need cairosvg or rsvg-convert only for the PNG; they check the SVG.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'
EVALS = ROOT / 'evals'

CRM = (EVALS / 'crm-postgres-full-document' / 'files' / 'schema.sql').read_text(encoding='utf-8')
SHOP = (EVALS / 'mysql-fk-type-mismatch' / 'files' / 'shop.sql').read_text(encoding='utf-8')
MIGRATIONS = EVALS / 'trigger-plain-request' / 'files' / 'migrations'


def run(script, *args, check=True):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                       capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f'{script} failed:\n{r.stdout}\n{r.stderr}')
    return r


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def parse(self, sql=None, path=None):
        if sql is not None:
            path = self.tmp / 'in.sql'
            path.write_text(sql, encoding='utf-8')
        out = self.tmp / 'model.json'
        run('parse_ddl.py', path, '-o', out, '--summary', self.tmp / 'summary.md')
        return out, json.loads(out.read_text(encoding='utf-8'))

    def render(self, model, labels=None, *extra):
        svg = self.tmp / 'er.svg'
        args = [model, '-o', svg, *extra]
        if labels is not None:
            lp = self.tmp / 'labels.json'
            lp.write_text(json.dumps(labels, ensure_ascii=False), encoding='utf-8')
            args += ['--labels', lp]
        run('render_er.py', *args)
        return svg.read_text(encoding='utf-8')


class ParseTests(Base):
    def test_postgres_crm(self):
        _, m = self.parse(CRM)
        self.assertEqual(m['dialect'], 'postgresql')
        self.assertEqual(m['stats']['tables'], 5)
        self.assertEqual(m['stats']['columns'], 23)
        self.assertEqual(m['stats']['foreign_keys'], 4)
        self.assertIn('partition_expired', {c['type'] for c in m['critical']})
        cands = {(c['child'], c['column']) for c in m['logical_link_candidates']}
        self.assertIn(('crm.note', 'company_id'), cands)

    def test_mysql_type_mismatch(self):
        _, m = self.parse(SHOP)
        self.assertEqual(m['dialect'], 'mysql')
        self.assertEqual([c['type'] for c in m['critical']], ['fk_type_mismatch'])
        orders = next(t for t in m['tables'] if t['name'] == 'orders')
        total = next(c for c in orders['columns'] if c['name'] == 'total')
        self.assertEqual(total.get('comment'), 'Сумма')

    def test_migrations_folder_final_state(self):
        _, m = self.parse(path=MIGRATIONS)
        self.assertEqual(len([t for t in m['tables'] if t.get('kind', 'table') == 'table']), 8)
        customer = next(t for t in m['tables'] if t['name'] == 'customer')
        self.assertIn('email', [c['name'] for c in customer['columns']])


class RenderTests(Base):
    LABELS = {'links': {'deal.company_id': 'заключает', 'deal.owner_id': 'ведёт',
                        'activity.deal_id': 'содержит', 'employee.manager_id': 'руководит'},
              'logical': [{'child': 'note.company_id', 'parent': 'company.id', 'label': 'имеет'}]}

    def labels_in(self, svg):
        rects = re.findall(r'<g class="labels">(.*?)</g>', svg, re.S)[0]
        return [tuple(map(float, r)) for r in
                re.findall(r'<rect x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="([\d.]+)"', rects)]

    def test_labels_inside_picture(self):
        model, _ = self.parse(CRM)
        svg = self.render(model, self.LABELS)
        width = float(re.search(r'<svg[^>]* width="([\d.]+)"', svg).group(1))
        labels = self.labels_in(svg)
        self.assertEqual(len(labels), 5)
        for x, y, w, h in labels:
            self.assertGreaterEqual(x, 0, 'label cut off on the left (self-loop on the outer side)')
            self.assertLessEqual(x + w, width, 'label cut off on the right')

    def test_mixed_parent_ends_get_own_lines(self):
        # company.id is the parent of deal.company_id (NOT NULL -> '||')
        # and of the logical note.company_id (nullable -> '|o'): two lines, two markers
        model, _ = self.parse(CRM)
        svg = self.render(model, self.LABELS)
        starts = [tuple(map(float, m)) for m in re.findall(r'<path d="M([\d.]+),([\d.]+)', svg)]
        company_x = max(x for x, _ in starts if sum(1 for q, _ in starts if q == x) >= 2)
        ys = sorted({y for x, y in starts if x == company_x})
        self.assertGreaterEqual(len(ys), 2, 'deal and note links share one line from company.id')

    def test_broken_fk_is_red(self):
        model, _ = self.parse(SHOP)
        svg = self.render(model)
        self.assertIn('stroke="#c62828"', svg)
        self.assertIn('FK не создастся', svg)
        model, _ = self.parse(CRM)  # no broken FK: no red, no legend row
        svg = self.render(model)
        self.assertNotIn('#c62828', svg)

    def test_no_small_steps(self):
        # the shop schema used to get a 3.5 px step on customer -> orders
        model, _ = self.parse(path=MIGRATIONS)
        svg = self.render(model, {'logical': [{'child': 'orders.coupon_id', 'parent': 'coupon.id'}]})
        for d in re.findall(r'<path d="([^"]+)"', svg):
            pts = [tuple(map(float, p.split(','))) for p in re.findall(r'[\d.]+,[\d.]+', d)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                if abs(x1 - x2) < 0.1:  # vertical segment
                    self.assertFalse(0.5 < abs(y1 - y2) < 6, f'small step in {d}')


class CheckTests(Base):
    def test_coverage(self):
        model, m = self.parse(SHOP)
        good = ['![Рисунок 1 — ER-диаграмма](er.png)']
        for t in m['tables']:
            good.append(f'### {t["name"]} (таблица `{t["name"]}`)')
            good += [f'| `{c["name"]}` | x |' for c in t['columns']]
        doc = self.tmp / 'draft.md'
        doc.write_text('\n'.join(good), encoding='utf-8')
        self.assertEqual(run('check_coverage.py', model, doc, check=False).returncode, 0)
        doc.write_text('\n'.join(good[:-1]) + '\nСм. `orders.no_such_column`.', encoding='utf-8')
        r = run('check_coverage.py', model, doc, check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn('qty', r.stdout)
        self.assertIn('no_such_column', r.stdout)

    def test_no_standard_refs(self):
        model, m = self.parse(SHOP)
        body = ['![Рисунок 1 — ER-диаграмма](er.png)', '## 3 Логическая структура', '### 3.1 Схема']
        for t in m['tables']:
            body.append(f'### {t["name"]} (таблица `{t["name"]}`)')
            body += [f'| `{c["name"]}` | x |' for c in t['columns']]
        doc = self.tmp / 'draft.md'
        doc.write_text('\n'.join(body + ['Подробнее в п. 3.1.']), encoding='utf-8')
        self.assertEqual(run('check_coverage.py', model, doc, check=False).returncode, 0,
                         'a cross-reference to the document\'s own section is fine')
        doc.write_text('\n'.join(body + ['Раздел описывает связи (ГОСТ Р 59795-2021, п. 8.9).']),
                       encoding='utf-8')
        r = run('check_coverage.py', model, doc, check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn('reference to a standard', r.stdout)
        self.assertEqual(run('check_coverage.py', model, doc, '--allow-standard-refs', check=False).returncode, 0)

    def test_lint(self):
        doc = self.tmp / 'draft.md'
        doc.write_text('Данная таблица является хранилищем. Одна строка — одна сделка.', encoding='utf-8')
        out = run('lint_style.py', doc, check=False).stdout
        self.assertIn('является', out)
        self.assertIn('Данная', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
