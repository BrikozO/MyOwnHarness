#!/usr/bin/env python3
"""Draw an ER diagram from model.json with orthogonal, row-anchored links.

Style (see references/er-diagram.md):
  * every link leaves the parent's PK row horizontally and enters the child's FK row
    horizontally; in between it runs only along horizontal and vertical segments;
  * parents are placed to the left, children to the right; reference tables sit next
    to the tables that use them;
  * every link gets its own vertical track in the gap between columns; track order is
    chosen to minimise crossings;
  * crow's-foot notation, optional verb labels on links ("формирует", "содержит");
  * entity = table name in the header, rows "key | column | type" with the database
    identifiers as they are (English), PK underlined, "NOT NULL" written in its own column;
  * verb labels on links are Russian (they read as a sentence from parent to child).

Output: SVG, plus PNG when cairosvg or rsvg-convert is available
(pip install --break-system-packages cairosvg).

Usage:
    python3 render_er.py model.json -o er.svg --labels labels.json --title "CRM: логическая структура"
    python3 render_er.py model.json -o er_sales.svg --tables deal,deal_contact,activity --labels labels.json
    python3 render_er.py model.json -o er_overview.svg --keys-only     # keys only, for big schemas

labels.json:
    {
      "entities": {"crm.deal": "Сделка"},          # used by the document text, not drawn
      "links":    {"deal.company_id": "заключает", "crm.activity.deal_id": "содержит"},
      "logical":  [{"child": "orders.customer_id", "parent": "customers.id", "label": "оформляет"}],
      "layout":   {"column": {"segment": 0}, "order": [["segment", "company"], ["deal"]]}
    }
A flat {"table": "Name"} dict is accepted as "entities". Link keys: child.fk_column
(with or without schema) or the FK constraint name. The verb reads from parent to child.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- geometry constants
FONT = "DejaVu Sans, Arial, Helvetica, sans-serif"
FS = 12          # attribute font size
HFS = 13         # entity title size
SFS = 10.5       # subtitle (table name) size
NN_FS = 10.5     # NOT NULL column
LFS = 11.5       # link label size
ROW_H = 21
HEAD_H1 = 26     # header with title only
HEAD_H2 = 40     # header with title + table name
PAD = 8
BOX_GAP_Y = 40   # vertical gap between boxes in a column (room for a corridor)
STUB = 34        # min distance from a box side to the nearest track (room for markers)
TRACK_SP = 14    # distance between parallel tracks
FACING_SP = 44   # wider spacing where two different links meet on one height
GAP_MIN = 80
MARGIN = 28
CORRIDOR_CLEAR = 8
MIXED_OFF = 5     # half distance between the two lines leaving one PK row with different parent ends

DASH = '7 5'      # logical links (no FK in the database)
COL_LINE = "#3a3a3a"
COL_BORDER = "#555555"
COL_HEAD = "#d9d9d9"
COL_TEXT = "#1f1f1f"
COL_MUTED = "#6b6b6b"
COL_STUB = "#9a9a9a"
COL_BROKEN = "#c62828"   # FK that the DBMS will not create («⛔ Критично» in the document)
BROKEN_FK = {'fk_type_mismatch', 'fk_target_not_unique', 'fk_missing_column'}


class Meter:
    """Text width: real font metrics via Pillow when available, else an estimate."""

    def __init__(self):
        self.fonts = {}
        try:
            from PIL import ImageFont  # noqa
            self.IF = ImageFont
        except Exception:
            self.IF = None

    def width(self, text: str, size: float, bold=False, italic=False) -> float:
        if self.IF is not None:
            name = ('DejaVuSans-Bold.ttf' if bold else
                    'DejaVuSans-Oblique.ttf' if italic else 'DejaVuSans.ttf')
            key = (name, size)
            if key not in self.fonts:
                try:
                    self.fonts[key] = self.IF.truetype(name, int(round(size * 4)))
                except Exception:
                    self.fonts[key] = None
            f = self.fonts[key]
            if f is not None:
                return f.getlength(text) / 4.0
        return len(text) * size * (0.66 if bold else 0.6)


M = Meter()


# ---------------------------------------------------------------- model -> entities
def load_labels(path):
    if not path:
        return {}, {}, {}
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if 'entities' in data or 'links' in data or 'layout' in data:
        return data.get('entities', {}), data.get('links', {}), data.get('layout', {})
    return data, {}, {}


def lookup(d, *keys):
    low = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        if k and k in d:
            return d[k]
        if k and str(k).lower() in low:
            return low[str(k).lower()]
    return None


class Box:
    def __init__(self, table, title, subtitle, rows, stub=False):
        self.t = table
        self.key = table['full_name']
        self.title, self.subtitle, self.rows, self.stub = title, subtitle, rows, stub
        self.head_h = HEAD_H2 if subtitle else HEAD_H1
        has_keys = any(r['key'] for r in rows)
        self.kw = (max(M.width(r['key'], 10) for r in rows) + 2 * PAD) if has_keys else 0
        self.nw = max([M.width(r['name'], FS) for r in rows] + [40]) + 2 * PAD
        self.tw = (max([M.width(r['type'], FS) for r in rows if r['type']] + [0]) + 2 * PAD) \
            if any(r['type'] for r in rows) else 0
        # NOT NULL is written out in its own column
        self.nnw = (M.width('NOT NULL', NN_FS) + 2 * PAD) if any(r['notnull'] for r in rows) else 0
        hw = max(M.width(title, HFS, bold=True), M.width(subtitle or '', SFS)) + 2 * PAD + 4
        inner = self.kw + self.nw + self.tw + self.nnw
        self.w = max(hw, inner)
        if self.w > inner:  # widen the name column to fill the box
            self.nw += self.w - inner
        self.h = self.head_h + len(rows) * ROW_H + 2
        self.x = self.y = 0.0
        self.col = 0

    def port_y(self, col_name):
        for i, r in enumerate(self.rows):
            if r['name'] == col_name and r.get('port', True):
                return self.y + self.head_h + i * ROW_H + ROW_H / 2
        return self.y + self.head_h / 2  # column hidden: attach to the header

    def port_off(self, col_name):
        return self.port_y(col_name) - self.y


def build_rows(t, keys_only=False, max_columns=0, only=None, keep=frozenset()):
    fk_cols = {c for fk in t['foreign_keys'] for c in fk['columns']}
    rows = []
    cols = sorted(t['columns'], key=lambda c: (not c['pk'],))
    if only is not None:
        cols = [c for c in cols if c['name'] in only or c['pk']]
    for c in cols:
        is_fk = c['name'] in fk_cols or bool(c.get('fk'))
        if keys_only and not (c['pk'] or is_fk or c['name'] in keep):
            continue
        key = ' '.join(k for k, on in (('PK', c['pk']), ('FK', is_fk),
                                        ('UQ', c.get('unique') and not c['pk'])) if on)
        typ = c.get('type') or ''
        typ = re.sub(r"^(enum|set)\((.{18}).*\)$", r"\1(\2…)", typ, flags=re.I)
        rows.append({'name': c['name'], 'type': typ, 'key': key, 'pk': c['pk'],
                     'fk': is_fk, 'notnull': not c['nullable'], 'keep': c['name'] in keep})
    if max_columns and not keys_only:
        keep, extra = [], 0
        plain = 0
        for r in rows:
            if r['pk'] or r['fk'] or r['keep']:
                keep.append(r)
            elif plain < max_columns:
                keep.append(r)
                plain += 1
            else:
                extra += 1
        if extra:
            keep.append({'name': f'… ещё {extra}', 'type': '', 'key': '', 'pk': False, 'fk': False,
                         'notnull': False, 'port': False, 'muted': True})
        rows = keep
    return rows


def card(t, fk):
    cols = {c['name']: c for c in t['columns']}
    mandatory = all(not cols[c]['nullable'] for c in fk['columns'] if c in cols)
    uniq = [u['columns'] for u in t['unique']] + [t['primary_key']] + \
           [i['columns'] for i in t['indexes'] if i['unique'] and not i.get('where')]
    one = any(u and set(u) == set(fk['columns']) for u in uniq) or \
        (len(fk['columns']) == 1 and cols.get(fk['columns'][0], {}).get('unique'))
    return ('||' if mandatory else '|o'), ('o|' if one else 'o{')


# ---------------------------------------------------------------- layout
def assign_columns(boxes, links, layout):
    keys = list(boxes)
    parents = {k: set() for k in keys}
    children = {k: set() for k in keys}
    for l in links:
        if l['p'] != l['c']:
            parents[l['c']].add(l['p'])
            children[l['p']].add(l['c'])
    # break cycles with a DFS: drop back edges for layering only
    state, back = {}, set()

    def dfs(u):
        state[u] = 1
        for v in sorted(children[u]):
            if state.get(v) == 1:
                back.add((u, v))
            elif v not in state:
                dfs(v)
        state[u] = 2
    for k in keys:
        if k not in state:
            dfs(k)
    par = {k: {p for p in parents[k] if (p, k) not in back} for k in keys}
    layer = {}

    def depth(k, seen=()):
        if k in layer:
            return layer[k]
        layer[k] = 0 if not par[k] else 1 + max(depth(p, seen + (k,)) for p in par[k])
        return layer[k]
    for k in keys:
        depth(k)
    # pull pure parents (reference tables) right next to their nearest child
    for _ in range(3):
        for k in keys:
            ch = [c for c in children[k] if (k, c) not in back]
            if not par[k] and ch:
                layer[k] = max(layer[k], min(layer[c] for c in ch) - 1)
    for k, v in (layout.get('column') or {}).items():
        for b in keys:
            if b == k or boxes[b].t['name'] == k:
                layer[b] = int(v)
    base = min(layer.values()) if layer else 0
    for k in keys:
        boxes[k].col = layer[k] - base
    return back


def order_columns(boxes, links, layout):
    ncol = max(b.col for b in boxes.values()) + 1
    cols = [[k for k in boxes if boxes[k].col == i] for i in range(ncol)]
    nbr = {k: [] for k in boxes}
    for l in links:
        if l['p'] != l['c']:
            nbr[l['p']].append(l['c'])
            nbr[l['c']].append(l['p'])
    pos = {k: i for col in cols for i, k in enumerate(col)}
    for it in range(8):
        rng = range(1, ncol) if it % 2 == 0 else range(ncol - 2, -1, -1)
        for i in rng:
            ref = i - 1 if it % 2 == 0 else i + 1
            def bary(k):
                ns = [pos[n] for n in nbr[k] if boxes[n].col == ref]
                return sum(ns) / len(ns) if ns else pos[k]
            cols[i].sort(key=bary)
            for j, k in enumerate(cols[i]):
                pos[k] = j
    # column 0 too: follow its neighbours in column 1
    if ncol > 1:
        cols[0].sort(key=lambda k: (sum(pos[n] for n in nbr[k] if boxes[n].col == 1) /
                                    max(1, len([n for n in nbr[k] if boxes[n].col == 1]))))
    for i, want in enumerate(layout.get('order') or []):
        if i < ncol:
            named = []
            for w in want:
                for k in cols[i]:
                    if (k == w or boxes[k].t['name'] == w) and k not in named:
                        named.append(k)
            cols[i] = named + [k for k in cols[i] if k not in named]
    return cols


def place_vertical(boxes, links, cols):
    for col in cols:
        y = MARGIN
        for k in col:
            boxes[k].y = y
            y += boxes[k].h + BOX_GAP_Y
    ncol = len(cols)
    for it in range(12):
        rng = list(range(ncol)) if it % 2 == 0 else list(range(ncol - 1, -1, -1))
        for i in rng:
            desired = {}
            for k in cols[i]:
                vals = []
                for l in links:
                    if l['p'] == l['c']:
                        continue
                    if l['p'] == k and boxes[l['c']].col != i:
                        vals.append(boxes[l['c']].port_y(l['ccol']) - boxes[k].port_off(l['pcol']))
                    if l['c'] == k and boxes[l['p']].col != i:
                        vals.append(boxes[l['p']].port_y(l['pcol']) - boxes[k].port_off(l['ccol']))
                desired[k] = sum(vals) / len(vals) if vals else boxes[k].y
            # forward pack keeping the order, then shift the block to balance
            ys, prev = [], None
            for k in cols[i]:
                y = desired[k] if prev is None else max(desired[k], prev)
                ys.append(y)
                prev = y + boxes[k].h + BOX_GAP_Y
            # backward pass: pull boxes up toward desired where room allows
            for j in range(len(ys) - 2, -1, -1):
                k, nk = cols[i][j], cols[i][j + 1]
                limit = ys[j + 1] - BOX_GAP_Y - boxes[k].h
                ys[j] = min(max(desired[k], ys[j]), limit) if desired[k] > ys[j] else ys[j]
            # centre the stack on what its links want instead of letting it grow downwards
            if ys:
                shift = sum(desired[k] - y for k, y in zip(cols[i], ys)) / len(ys)
                ys = [y + shift for y in ys]
            for k, y in zip(cols[i], ys):
                boxes[k].y = y
    straighten(boxes, links, cols)
    top = min(b.y for b in boxes.values())
    for b in boxes.values():
        b.y += MARGIN + 40 - top  # room for the title


def straighten(boxes, links, cols):
    """Remove small jogs: if a link's PK and FK rows almost line up, move one box to align them."""
    def fits(b, ny):
        for k in cols[b.col]:
            o = boxes[k]
            if o is not b and ny < o.y + o.h + 16 and o.y < ny + b.h + 16:
                return False
        return True
    moved = set()
    for _ in range(3):
        for l in links:
            P, C = boxes[l['p']], boxes[l['c']]
            if P is C or P.col == C.col:
                continue
            d = P.port_y(l['pcol']) - C.port_y(l['ccol'])
            if 0.5 < abs(d) <= 2.5 * ROW_H:
                for b, nd in ((C, d), (P, -d)):
                    if b.key in moved:
                        continue
                    if fits(b, b.y + nd):
                        b.y += nd
                        moved.add(b.key)
                        break


# ---------------------------------------------------------------- routing
class Part:
    """A piece of a route inside one gap: two horizontal attachments joined by a vertical."""

    def __init__(self, link, gap, a, b):
        self.link, self.gap = link, gap
        self.a, self.b = a, b          # (side 'L'|'R', y): where each horizontal comes from
        self.x = None

    @property
    def ymin(self):
        return min(self.a[1], self.b[1])

    @property
    def ymax(self):
        return max(self.a[1], self.b[1])

    @property
    def straight(self):
        return abs(self.a[1] - self.b[1]) < 0.5


def crossings(order):
    n = 0
    for i, A in enumerate(order):
        for B in order[i + 1:]:          # A is left of B
            for side, y in (A.a, A.b):
                if side == 'R' and B.ymin + 0.5 < y < B.ymax - 0.5:
                    n += 1
            for side, y in (B.a, B.b):
                if side == 'L' and A.ymin + 0.5 < y < A.ymax - 0.5:
                    n += 1
            # two links on one horizontal line overlap: A's line going right, B's coming from the left
            for sa, ya in (A.a, A.b):
                for sb, yb in (B.a, B.b):
                    if sa == 'R' and sb == 'L' and abs(ya - yb) < 0.5:
                        n += 100
    return n


def best_order(parts):
    parts = sorted(parts, key=lambda p: (p.ymin, p.ymax))
    if len(parts) <= 7:
        return list(min(itertools.permutations(parts), key=lambda o: (crossings(o), 0)))
    cur, best = parts[:], crossings(parts)
    improved = True
    while improved:
        improved = False
        for i in range(len(cur) - 1):
            cur[i], cur[i + 1] = cur[i + 1], cur[i]
            c = crossings(cur)
            if c < best:
                best, improved = c, True
            else:
                cur[i], cur[i + 1] = cur[i + 1], cur[i]
    return cur


def free_y(boxes, cols_between, lo, hi, taken, target):
    blocks = sorted((b.y - CORRIDOR_CLEAR, b.y + b.h + CORRIDOR_CLEAR)
                    for b in boxes.values() if b.col in cols_between)
    # candidate free intervals
    free, cur = [], lo
    for a, z in blocks:
        if a > cur:
            free.append((cur, a))
        cur = max(cur, z)
    free.append((cur, hi))
    best = None
    for a, z in free:
        if z - a < 8:
            continue
        y = min(max(target, a + 6), z - 6)
        for step in range(0, 400, 10):        # avoid other corridors in the same gaps
            for cand in (y + step, y - step):
                if a + 4 <= cand <= z - 4 and all(abs(cand - t) >= 10 for t in taken):
                    score = abs(cand - target)
                    if best is None or score < best[0]:
                        best = (score, cand)
                    break
            else:
                continue
            break
    return best[1] if best else hi


def route(boxes, links, cols):
    ncol = len(cols)
    parts_by_gap = {g: [] for g in range(ncol + 1)}
    corridors = {}  # gap-range -> list of y
    lo = min(b.y for b in boxes.values()) - 60
    hi = max(b.y + b.h for b in boxes.values()) + 60
    # Links leaving one PK row towards one side share a line (a bus) and one parent marker.
    # If their parent ends differ (FK NOT NULL -> '||', nullable -> '|o'), one shared marker
    # would hide the difference: such a row gets two parallel lines, one per kind.
    kinds = {}
    for l in links:
        cp, cc = boxes[l['p']].col, boxes[l['c']].col
        if cp != cc:
            dy = boxes[l['c']].port_y(l['ccol']) - boxes[l['p']].port_y(l['pcol'])
            kinds.setdefault((l['p'], l['pcol'], cc > cp), {}).setdefault(l['lm'], []).append(dy)
    for l in links:
        P, C = boxes[l['p']], boxes[l['c']]
        py, cy = P.port_y(l['pcol']), C.port_y(l['ccol'])
        cp, cc = P.col, C.col
        ks = kinds.get((l['p'], l['pcol'], cc > cp), {})
        if cp != cc and len(ks) > 1:
            # the kind whose children lie higher takes the upper line: fewer crossings
            mean = {k: sum(v) / len(v) for k, v in ks.items()}
            other = next(k for k in ks if k != l['lm'])
            up = (mean[l['lm']], l['lm']) < (mean[other], other)
            py += -MIXED_OFF if up else MIXED_OFF
            l['mhalf'] = 4
            # still inside the child's FK row: go straight instead of a small step
            if abs(cy - py) <= MIXED_OFF + 0.5:
                cy = py
        if cc > cp:
            gS, gE, sS, sE = cp + 1, cc, 'R', 'L'
        elif cc < cp:
            gS, gE, sS, sE = cp, cc + 1, 'L', 'R'
        else:
            # same column / self-reference: loop out of the less busy side
            busy = {'R': 0, 'L': 0}
            for o in links:
                if o is l or o['p'] == o['c']:
                    continue
                for bk, side in ((o['p'], 'R' if boxes[o['c']].col > boxes[o['p']].col else 'L'),
                                 (o['c'], 'L' if boxes[o['c']].col > boxes[o['p']].col else 'R')):
                    if bk in (l['p'], l['c']) and boxes[o['c']].col != boxes[o['p']].col:
                        busy[side] += 1
            side = 'L' if busy['L'] < busy['R'] else 'R'
            gS = gE = (cp + 1) if side == 'R' else cp
            sS = sE = side
        l.update(py=py, cy=cy, sS=sS, sE=sE)
        if gS == gE:
            # attachments seen from inside the gap: a box on the left of the gap is side 'L'
            a = ('L' if sS == 'R' else 'R', py)
            b = ('L' if sE == 'R' else 'R', cy)
            p = Part(l, gS, a, b)
            parts_by_gap[gS].append(p)
            l['parts'] = [p]
            l['corr'] = None
        else:
            lo_g, hi_g = min(gS, gE), max(gS, gE)
            between = set(range(lo_g, hi_g))
            taken = [y for (g1, g2), ys in corridors.items() if not (g2 < lo_g or g1 > hi_g) for y in ys]
            target = (py + cy) / 2
            yc = free_y(boxes, between, lo, hi, taken, target)
            # a corridor a few px off the PK or FK row makes a small step: snap to the row
            # when that height is free as well
            for snap in (py, cy):
                clear = all(not (b.y - CORRIDOR_CLEAR / 2 < snap < b.y + b.h + CORRIDOR_CLEAR / 2)
                            for b in boxes.values() if b.col in between)
                if 0.5 < abs(yc - snap) < 12 and clear and all(abs(snap - t) >= 10 for t in taken):
                    yc = snap
                    break
            corridors.setdefault((lo_g, hi_g), []).append(yc)
            right = gE > gS
            p1 = Part(l, gS, ('L' if sS == 'R' else 'R', py), ('R' if right else 'L', yc))
            p2 = Part(l, gE, ('L' if right else 'R', yc), ('L' if sE == 'R' else 'R', cy))
            parts_by_gap[gS].append(p1)
            parts_by_gap[gE].append(p2)
            l['parts'] = [p1, p2]
            l['corr'] = yc
    return parts_by_gap


def track_steps(order):
    """Distances between neighbouring tracks. Where a link's line runs right and another link's
    line arrives from the left on the same height, keep their corners well apart so the two
    lines do not read as one."""
    steps = []
    for i in range(1, len(order)):
        wide = False
        for A in order[:i]:
            for B in order[i:]:
                for sa, ya in (A.a, A.b):
                    for sb, yb in (B.a, B.b):
                        # A's line comes in from the left, B's goes out to the right at the
                        # same height: the corners must be far apart to read as two lines
                        if sa == 'L' and sb == 'R' and abs(ya - yb) < 6:
                            wide = True
        steps.append(FACING_SP if wide else TRACK_SP)
    return steps


def place_horizontal(boxes, cols, parts_by_gap, links, title_w):
    ncol = len(cols)
    colw = [max(boxes[k].w for k in col) for col in cols]
    orders, gapw = {}, {}
    for g, parts in parts_by_gap.items():
        bent = [p for p in parts if not p.straight]
        orders[g] = best_order(bent) if bent else []
        k = len(orders[g])
        steps = track_steps(orders[g])
        need = 2 * STUB + sum(steps)
        labw = max([M.width(p.link['label'], LFS) for p in parts if p.link.get('label')] + [0])
        if g in (0, ncol) and bent:
            # outer gap: tracks hug the boxes, the label goes on the free outer side
            need = STUB + sum(steps) + (labw + 30 if labw else MARGIN)
        elif labw:
            need = max(need, labw + 2 * STUB)
        if parts:
            gapw[g] = max(GAP_MIN, need)
        else:
            gapw[g] = MARGIN if g in (0, ncol) else GAP_MIN
    x = gapw[0]
    gx = {}
    colx = []
    for i in range(ncol):
        gx[i] = (x - gapw[i], x)
        colx.append(x)
        x += colw[i] + gapw[i + 1]
    gx[ncol] = (x - gapw[ncol], x)
    for i, col in enumerate(cols):
        for k in col:
            boxes[k].x = colx[i] + (colw[i] - boxes[k].w) / 2
    for g, order in orders.items():
        a, z = gx[g]
        mid = (a + z) / 2
        steps = track_steps(order)
        x0 = mid - sum(steps) / 2
        if g == 0 and order:
            x0 = z - STUB - sum(steps)
        elif g == ncol and order and ncol:
            x0 = a + STUB
        for i, p in enumerate(order):
            p.x = x0 + sum(steps[:i])
        for p in parts_by_gap[g]:
            if p.straight:
                p.x = mid
    width = max(x, title_w + 2 * MARGIN)
    return width, gx


def polyline(l, boxes):
    P, C = boxes[l['p']], boxes[l['c']]
    sx = P.x + P.w if l['sS'] == 'R' else P.x
    ex = C.x + C.w if l['sE'] == 'R' else C.x
    pts = [(sx, l['py'])]
    if l['corr'] is None:
        p = l['parts'][0]
        if not p.straight:
            pts += [(p.x, l['py']), (p.x, l['cy'])]
    else:
        p1, p2 = l['parts']
        pts += [(p1.x, l['py']), (p1.x, l['corr']), (p2.x, l['corr']), (p2.x, l['cy'])]
    pts.append((ex, l['cy']))
    # drop zero-length / collinear points
    clean = [pts[0]]
    for q in pts[1:]:
        if abs(q[0] - clean[-1][0]) < 0.1 and abs(q[1] - clean[-1][1]) < 0.1:
            continue
        clean.append(q)
    out = [clean[0]]
    for i in range(1, len(clean) - 1):
        a, b, c = out[-1], clean[i], clean[i + 1]
        if (abs(a[0] - b[0]) < 0.1 and abs(b[0] - c[0]) < 0.1) or (abs(a[1] - b[1]) < 0.1 and abs(b[1] - c[1]) < 0.1):
            continue
        out.append(b)
    out.append(clean[-1])
    return out


# ---------------------------------------------------------------- drawing
def marker(x, y, d, kind, half=6):
    """Crow's-foot end at box side (x, y); d = +1 if the line leaves to the right, -1 to the left.
    half is the half-height of bars and toes (smaller where two lines leave one row)."""
    s = []
    def line(x1, y1, x2, y2):
        s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    def circle(cx):
        s.append(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="{min(4.5, half - 0.5):.1f}" fill="#fff"/>')
    inner, outer = kind[0], kind[1]
    if kind in ('o{', '|{'):
        # crow's foot: toes on the box side, joint 13 px out
        line(x, y - half, x + 13 * d, y)
        line(x, y + half, x + 13 * d, y)
        if kind == '|{':
            line(x + 17 * d, y - half, x + 17 * d, y + half)
        else:
            circle(x + 21 * d)
        return ''.join(s)
    # one-sided: inner symbol is the maximum (bar), outer is the minimum (bar or circle)
    line(x + 8 * d, y - half, x + 8 * d, y + half)
    if kind in ('||',):
        line(x + 13 * d, y - half, x + 13 * d, y + half)
    else:
        circle(x + 18 * d)
    return ''.join(s)


def text(x, y, s, size=FS, weight='normal', anchor='start', fill=COL_TEXT, style='', deco=''):
    extra = f' font-style="{style}"' if style else ''
    extra += f' text-decoration="{deco}"' if deco else ''
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{fill}"{extra}>{escape(s)}</text>')


def draw_box(b):
    s = [f'<g class="entity" id="{escape(re.sub(r"[^A-Za-z0-9_-]", "_", b.key))}">']
    dash = ' stroke-dasharray="5 4"' if b.stub else ''
    head_fill = '#efefef' if b.stub else COL_HEAD
    # square corners: tables are drawn as plain rectangles
    s.append(f'<rect x="{b.x:.1f}" y="{b.y:.1f}" width="{b.w:.1f}" height="{b.h:.1f}" '
             f'fill="#ffffff" stroke="{COL_BORDER}" stroke-width="1.2"{dash}/>')
    s.append(f'<rect x="{b.x + 0.6:.1f}" y="{b.y + 0.6:.1f}" width="{b.w - 1.2:.1f}" height="{b.head_h - 0.6:.1f}" '
             f'fill="{head_fill}" stroke="none"/>')
    s.append(f'<line x1="{b.x:.1f}" y1="{b.y + b.head_h:.1f}" x2="{b.x + b.w:.1f}" y2="{b.y + b.head_h:.1f}" '
             f'stroke="{COL_BORDER}" stroke-width="1.2"/>')
    s.append(text(b.x + PAD, b.y + 18, b.title, HFS, 'bold'))
    if b.subtitle:
        s.append(text(b.x + PAD, b.y + 33, b.subtitle, SFS, fill=COL_MUTED))
    # column dividers like a table
    x1 = b.x + b.kw
    x2 = b.x + b.kw + b.nw
    y0, y1 = b.y + b.head_h, b.y + b.h
    if b.kw:
        s.append(f'<line x1="{x1:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#bdbdbd"/>')
    if b.tw:
        s.append(f'<line x1="{x2:.1f}" y1="{y0:.1f}" x2="{x2:.1f}" y2="{y1:.1f}" stroke="#bdbdbd"/>')
    x3 = x2 + b.tw
    if b.nnw:
        s.append(f'<line x1="{x3:.1f}" y1="{y0:.1f}" x2="{x3:.1f}" y2="{y1:.1f}" stroke="#bdbdbd"/>')
    for i, r in enumerate(b.rows):
        ty = y0 + i * ROW_H + ROW_H / 2 + FS * 0.36
        if r['key']:
            s.append(text(b.x + PAD, ty, r['key'], 10, 'bold' if r['pk'] else 'normal', fill=COL_MUTED))
        fill = COL_MUTED if r.get('muted') else COL_TEXT
        s.append(text(x1 + PAD, ty, r['name'], FS, fill=fill))
        if r['pk']:  # underline drawn as a line: PNG converters ignore text-decoration
            uw = M.width(r['name'], FS)
            s.append(f'<line x1="{x1 + PAD:.1f}" y1="{ty + 2.2:.1f}" x2="{x1 + PAD + uw:.1f}" y2="{ty + 2.2:.1f}" '
                     f'stroke="{COL_TEXT}" stroke-width="0.9"/>')
        if r['type']:
            s.append(text(x2 + PAD, ty, r['type'], FS, fill=COL_MUTED))
        if r['notnull'] and b.nnw:
            s.append(text(x3 + PAD, ty - 0.5, 'NOT NULL', NN_FS, fill=COL_MUTED))
    s.append('</g>')
    return ''.join(s)


def seg_hits(rect, segs):
    x0, y0, x1, y1 = rect
    for (ax, ay), (bx, by) in segs:
        sx0, sx1 = min(ax, bx) - 1, max(ax, bx) + 1
        sy0, sy1 = min(ay, by) - 1, max(ay, by) + 1
        if not (x1 < sx0 or x0 > sx1 or y1 < sy0 or y0 > sy1):
            return True
    return False


def collinear_overlap(s1, s2):
    (ax, ay), (bx, by) = s1
    (cx, cy), (dx, dy) = s2
    if abs(ay - by) < 0.1 and abs(cy - dy) < 0.1 and abs(ay - cy) < 0.5:
        return min(max(ax, bx), max(cx, dx)) - max(min(ax, bx), min(cx, dx)) > 4
    if abs(ax - bx) < 0.1 and abs(cx - dx) < 0.1 and abs(ax - cx) < 0.5:
        return min(max(ay, by), max(cy, dy)) - max(min(ay, by), min(cy, dy)) > 4
    return False


def place_label(l, pts, placed, boxes, other_segs=(), marker_zones=(), bounds=None):
    lab = l.get('label')
    if not lab:
        return None
    w, h = M.width(lab, LFS) + 8, 16

    def overlap(r, q):
        return not (r[2] < q[0] or r[0] > q[2] or r[3] < q[1] or r[1] > q[3])

    def cost(r, own_other):
        c = 0
        c += sum(1000 for b in boxes.values() if overlap(r, (b.x - 2, b.y - 2, b.x + b.w + 2, b.y + b.h + 2)))
        c += sum(300 for z in marker_zones if overlap(r, z))
        c += sum(200 for q in placed if overlap(r, q))
        c += 60 if seg_hits(r, own_other) else 0
        c += sum(40 for sg in other_segs if seg_hits(r, [sg]))
        if bounds and (r[0] < bounds[0] or r[1] < bounds[1] or r[2] > bounds[2]):
            c += 1000  # outside the picture: the label would be cut off
        return c

    best = None
    segs = list(zip(pts, pts[1:]))
    for i, ((x1, y1), (x2, y2)) in enumerate(segs):
        vertical = abs(x1 - x2) < 0.1
        own_other = [sg for j, sg in enumerate(segs) if j != i]
        length = abs(x2 - x1) + abs(y2 - y1)
        # a segment shared with another link (a bus) does not tell whose label it is
        shared = 150 if any(collinear_overlap(((x1, y1), (x2, y2)), sg) for sg in other_segs) else 0
        for t in (0.5, 0.35, 0.65, 0.2, 0.8):
            cx, cy = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            cands = ([(cx + w / 2 + 5, cy, 0), (cx - w / 2 - 5, cy, 0)] if vertical
                     else [(cx, cy - 10, 0), (cx, cy + 12, 0)])
            if not vertical and length > w + 16:
                # fallback: on the line itself, which it breaks (white backing) - unambiguous
                # where neighbouring lines leave no room beside it
                cands.append((cx, cy, 45))
            for ccx, ccy, extra in cands:
                r = (ccx - w / 2, ccy - h / 2, ccx + w / 2, ccy + h / 2)
                # prefer long segments and the middle of the route
                score = cost(r, own_other) + shared + extra + (0 if length > (h + 8 if vertical else w + 8) else 25) \
                    + abs(i - (len(segs) - 1) / 2) * 2 + abs(t - 0.5) * 10
                if best is None or score < best[0]:
                    best = (score, r, ccx, ccy)
    _, rect, cx, cy = best
    placed.append(rect)
    return rect, cx, cy


def legend(x, y, logical=False, used=None, broken=False):
    items = [('||', 'ровно один'), ('|o', 'ноль или один'), ('o{', 'ноль или много'), ('|{', 'один или много')]
    if used:
        # only the line ends that appear on this diagram ('o|' is drawn as '|o')
        used = {'|o' if k == 'o|' else k for k in used}
        items = [it for it in items if it[0] in used]
    w, rowh = 236, 20
    h = 30 + len(items) * rowh + (2 + logical + broken) * rowh + 8
    s = [f'<g class="legend"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fafafa" stroke="#bbbbbb"/>',
         text(x + 10, y + 19, 'Обозначения', FS, 'bold')]
    yy = y + 30
    for kind, lab in items:
        cy = yy + rowh / 2
        s.append(f'<g stroke="{COL_LINE}" stroke-width="1.3" fill="none">'
                 f'<line x1="{x + 14}" y1="{cy}" x2="{x + 56}" y2="{cy}"/>{marker(x + 56, cy, -1, kind)}</g>')
        s.append(text(x + 66, cy + 4, lab, 11))
        yy += rowh
    if logical:
        cy = yy + rowh / 2
        s.append(f'<line x1="{x + 14}" y1="{cy}" x2="{x + 56}" y2="{cy}" stroke="{COL_LINE}" '
                 f'stroke-width="1.3" stroke-dasharray="{DASH}"/>')
        s.append(text(x + 66, cy + 4, 'логическая связь без FK', 11))
        yy += rowh
    if broken:
        cy = yy + rowh / 2
        s.append(f'<line x1="{x + 14}" y1="{cy}" x2="{x + 56}" y2="{cy}" stroke="{COL_BROKEN}" stroke-width="1.3"/>')
        s.append(text(x + 66, cy + 4, 'FK не создастся (критично)', 11))
        yy += rowh
    s.append(text(x + 14, yy + 14, 'PK, FK, UQ — ключи', 11, fill=COL_MUTED))
    s.append(text(x + 14, yy + 14 + rowh, 'NOT NULL — обязательный атрибут', 11, fill=COL_MUTED))
    s.append('</g>')
    return ''.join(s), w, h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('model')
    ap.add_argument('-o', '--output', default='er.svg', help='.svg path; a .png is written next to it')
    ap.add_argument('--labels', help='JSON with entity names, link verbs and layout hints')
    ap.add_argument('--tables', help='comma-separated tables (name or schema.name) or @file')
    ap.add_argument('--title')
    ap.add_argument('--keys-only', action='store_true', help='show only PK/FK rows (overview of a big schema)')
    ap.add_argument('--no-types', action='store_true')
    ap.add_argument('--max-columns', type=int, default=0,
                    help='show at most N non-key attributes per entity (PK/FK are always shown)')
    ap.add_argument('--no-stubs', action='store_true', help='do not draw referenced tables outside --tables')
    ap.add_argument('--no-legend', action='store_true')
    ap.add_argument('--png-scale', type=float, default=2.0)
    args = ap.parse_args()

    model = json.loads(Path(args.model).read_text(encoding='utf-8'))
    ent_labels, link_labels, layout = load_labels(args.labels)
    tables = [t for t in model['tables'] if t.get('kind', 'table') == 'table']
    by = {t['full_name']: t for t in tables}
    if args.tables:
        spec = args.tables
        if spec.startswith('@'):
            spec = Path(spec[1:]).read_text(encoding='utf-8').replace('\n', ',')
        sel = []
        for w in [s.strip() for s in spec.split(',') if s.strip()]:
            hit = by.get(w) or next((t for t in tables if t['name'] == w), None)
            if hit is None:
                print(f'! table {w} not found in the model', file=sys.stderr)
            elif hit not in sel:
                sel.append(hit)
        tables = sel
    names = {t['full_name'] for t in tables}

    def title_of(t):
        # the box shows the database identifiers only (table and column names as in the DDL);
        # Russian entity names belong to the document text, not to the diagram
        tn = t['name'] if not t.get('schema') or t['schema'] in ('public', 'dbo') else t['full_name']
        return tn, None

    # logical links: no FK in the database, but the data is linked by meaning (drawn dashed)
    raw = json.loads(Path(args.labels).read_text(encoding='utf-8')) if args.labels else {}
    logical = []
    for item in raw.get('logical', []) if isinstance(raw, dict) else []:
        cparts, pparts = item['child'].rsplit('.', 1), item['parent'].rsplit('.', 1)
        ct = by.get(cparts[0]) or next((t for t in tables if t['name'] == cparts[0]), None)
        all_by = {t['full_name']: t for t in model['tables']}
        pt = all_by.get(pparts[0]) or next((t for t in model['tables'] if t['name'] == pparts[0]), None)
        if ct is None or pt is None:
            print(f"! logical link {item['child']} -> {item['parent']}: table not drawn or not found", file=sys.stderr)
            continue
        logical.append((ct, cparts[1], pt, pparts[1] if len(pparts) > 1 else pt['primary_key'][0], item.get('label')))
    keep = {}
    for ct, ccol, pt, pcol, _ in logical:
        keep.setdefault(ct['full_name'], set()).add(ccol)
        keep.setdefault(pt['full_name'], set()).add(pcol)

    boxes = {}
    for t in tables:
        ttl, sub = title_of(t)
        boxes[t['full_name']] = Box(t, ttl, sub, build_rows(t, args.keys_only, args.max_columns,
                                                             keep=frozenset(keep.get(t['full_name'], ()))))
    broken = {(c.get('table'), col) for c in model.get('critical', [])
              if c.get('type') in BROKEN_FK for col in c.get('columns') or []}
    links = []
    for t in tables:
        for fk in t['foreign_keys']:
            pfn = fk.get('ref_full_name')
            if pfn not in names:
                if args.no_stubs or pfn not in by:
                    continue
                if pfn not in boxes:
                    pt = by[pfn]
                    ttl, sub = title_of(pt)
                    boxes[pfn] = Box(pt, ttl, sub, build_rows(pt, True, 0, only=set()), stub=True)
                b = boxes[pfn]
                need = set(fk['ref_columns']) | {r['name'] for r in b.rows}
                boxes[pfn] = Box(by[pfn], b.title, b.subtitle, build_rows(by[pfn], True, 0, only=need), stub=True)
            left, right = card(t, fk)
            ccol = fk['columns'][0]
            label = lookup(link_labels, f"{t['full_name']}.{ccol}", f"{t['name']}.{ccol}", fk.get('name'))
            links.append({'p': pfn, 'c': t['full_name'],
                          'pcol': fk['ref_columns'][0] if fk['ref_columns'] else by[pfn]['primary_key'][0],
                          'ccol': ccol, 'lm': left, 'rm': right, 'label': label,
                          'broken': any((tn, c) in broken for tn in (t['full_name'], t['name'])
                                        for c in fk['columns'])})
    for ct, ccol, pt, pcol, label in logical:
        if pt['full_name'] not in boxes:
            if args.no_stubs:
                continue
            ttl, sub = title_of(pt)
            boxes[pt['full_name']] = Box(pt, ttl, sub, build_rows(pt, True, 0, only={pcol}), stub=True)
        cc = next((c for c in ct['columns'] if c['name'] == ccol), None)
        if cc is None:
            print(f'! logical link: column {ct["name"]}.{ccol} not found', file=sys.stderr)
            continue
        uniq = [u['columns'] for u in ct['unique']] + [ct['primary_key']]
        one = cc.get('unique') or any(u == [ccol] for u in uniq)
        links.append({'p': pt['full_name'], 'c': ct['full_name'], 'pcol': pcol, 'ccol': ccol,
                      'lm': '|o' if cc['nullable'] else '||', 'rm': 'o|' if one else 'o{',
                      'label': label, 'logical': True})
    if not boxes:
        sys.exit('nothing to draw')

    assign_columns(boxes, links, layout)
    cols = order_columns(boxes, links, layout)
    place_vertical(boxes, links, cols)
    parts = route(boxes, links, cols)
    title = args.title or ''
    width, _ = place_horizontal(boxes, cols, parts, links, M.width(title, 15, bold=True))

    # ---- svg
    body, placed = [], []
    paths = [(l, polyline(l, boxes)) for l in links]
    lines_svg = []
    ends = {}
    for l, pts in paths:
        d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        dash = f' stroke-dasharray="{DASH}"' if l.get('logical') else ''
        red = f' stroke="{COL_BROKEN}"' if l.get('broken') else ''
        lines_svg.append(f'<path d="{d}" fill="none"{dash}{red}/>')
        (sx, sy), (ex, ey) = pts[0], pts[-1]
        ds = 1 if l['sS'] == 'R' else -1
        de = 1 if l['sE'] == 'R' else -1
        # links leaving one PK row on one side share the line there: one marker per port
        h = l.get('mhalf', 6)
        b = bool(l.get('broken'))
        ends.setdefault((round(sx, 1), round(sy, 1), ds), []).append((l['lm'], h, b))
        ends.setdefault((round(ex, 1), round(ey, 1), de), []).append((l['rm'], h, b))
    for (x, y, d), kinds in ends.items():
        # one marker per port; a shared port holds links of one kind only (see route)
        kind = kinds[0][0]
        m = marker(x, y, d, kind, min(k[1] for k in kinds))
        if all(k[2] for k in kinds):
            m = f'<g stroke="{COL_BROKEN}">{m}</g>'
        lines_svg.append(m)
    labels_svg = []
    zones = []
    for (x, y, d), _k in ends.items():
        x2 = x + 26 * d
        zones.append((min(x, x2), y - 8, max(x, x2), y + 8))
    for l, pts in paths:
        others = [seg for o, opts in paths if o is not l for seg in zip(opts, opts[1:])]
        r = place_label(l, pts, placed, boxes, others, zones, bounds=(4, 4, width - 4))
        if r:
            rect, cx, cy = r
            labels_svg.append(f'<rect x="{rect[0]:.1f}" y="{rect[1]:.1f}" width="{rect[2] - rect[0]:.1f}" '
                              f'height="{rect[3] - rect[1]:.1f}" fill="#ffffff" opacity="0.92"/>')
            labels_svg.append(text(cx, cy + LFS * 0.36, l['label'], LFS, anchor='middle'))
    height = max(b.y + b.h for b in boxes.values()) + MARGIN
    for rect in placed:
        height = max(height, rect[3] + MARGIN)
    leg_svg = ''
    if not args.no_legend:
        lw, lh = 236, 30 + 6 * 20 + 8
        # bottom-right corner, below everything
        lx, ly = width - lw - MARGIN, height
        leg_svg, lw, lh = legend(lx, ly, any(l.get('logical') for l in links),
                                 {k for l in links for k in (l['lm'], l['rm'])},
                                 any(l.get('broken') for l in links))
        height = ly + lh + MARGIN
    corridor_low = max([l['corr'] for l in links if l['corr'] is not None] + [0])
    height = max(height, corridor_low + MARGIN)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
           f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="{FONT}">',
           f'<rect width="100%" height="100%" fill="#ffffff"/>']
    if title:
        svg.append(text(MARGIN, MARGIN + 6, title, 15, 'bold'))
    svg.append(f'<g class="links" stroke="{COL_LINE}" stroke-width="1.3" fill="none">{"".join(lines_svg)}</g>')
    svg.extend(draw_box(b) for b in boxes.values())
    svg.append(f'<g class="labels">{"".join(labels_svg)}</g>')
    svg.append(leg_svg)
    svg.append('</svg>')
    out = Path(args.output)
    if out.suffix.lower() != '.svg':
        out = out.with_suffix('.svg')
    out.write_text('\n'.join(svg), encoding='utf-8')
    png = out.with_suffix('.png')
    ok = False
    try:
        import cairosvg
        cairosvg.svg2png(url=str(out), write_to=str(png), scale=args.png_scale)
        ok = True
    except Exception:
        if shutil.which('rsvg-convert'):
            ok = subprocess.run(['rsvg-convert', '-z', str(args.png_scale), '-o', str(png), str(out)]).returncode == 0
    n_cross = sum(crossings(sorted([q for q in p if not q.straight], key=lambda q: q.x))
                  for p in parts.values())
    print(f'OK: {out}' + (f' and {png}' if ok else ' (no PNG: pip install --break-system-packages cairosvg)'))
    print(f'Entities {len(boxes)} (stubs {sum(b.stub for b in boxes.values())}), links {len(links)} '
          f'(logical {sum(1 for l in links if l.get("logical"))}), '
          f'columns {len(cols)}, size {width:.0f}x{height:.0f}px, track crossings {n_cross}.')
    if len(tables) > 15 and not args.keys_only:
        print('! More than 15 entities on one diagram are hard to read: draw an overview (--keys-only) '
              'and one diagram per subject area (--tables).')


if __name__ == '__main__':
    main()
