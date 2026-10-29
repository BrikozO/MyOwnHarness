#!/usr/bin/env python3
"""Find verbal clutter in a Russian document (information style, «Пиши, сокращай»).

Flags bureaucratese (канцелярит), filler and intensifiers, evaluations without facts,
vagueness, impersonal passive, clichés and sentences longer than --max-words.
Code (```...```, `...`) is skipped. Domain terms that look like stop words are excluded:
«данные», «уникальный ключ», «информационное обеспечение», «хранится», «произведение».

A hit is a reason to reread the phrase, not a verdict: if the word carries meaning, keep it.

Usage:
    python3 lint_style.py draft.md [--max-words 25]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

W = r'[а-яёА-ЯЁ-]'
RULES = [
    ('канцелярит', r'\b(осуществл\w*|является|являются|являющ\w*|данн(?:ый|ая|ое|ого|ой|ом|ую)\b|'
                   r'в рамках|в целях|с целью|в случае(?: если)?|посредством|в настоящее время|'
                   r'имеет место|при помощи|в связи с|вследствие|ввиду|в части\b|в качестве|путём|путем|'
                   r'(?:необходимо|следует|стоит|нужно) отметить|обращаем внимание|'
                   r'проведени\w*|соответствующ\w*)',
     'replace with a verb or a precise word: «является» -> dash, «осуществляет запись» -> «записывает»'),
    ('пассив', r'\b(?:осуществля|производ|выполня|реализу|обеспечива|предоставля|формиру)(?:ит|ет|ют|ят)ся\b',
     'name the actor: «сервис заказов записывает», «СУБД проверяет»'),
    ('вводное/усилитель', r'\b(очень|весьма|достаточно|крайне|максимально|безусловно|конечно|как правило|'
                          r'по сути|фактически|в принципе|практически|собственно|в общем|как известно|'
                          r'действительно|абсолютно|вообще|довольно|по возможности)\b',
     'delete it; if meaning changes, give the fact instead'),
    ('оценка без факта', r'\b(эффективн\w*|современн\w*|удобн\w*|надёжн\w*|надежн\w*|гибк\w*|оптимальн\w*|'
                         r'качественн\w*|мощн\w*|интуитивн\w*|быстр(?:ый|ая|ое|ые|о|ого|ому|ым|ых)\b|'
                         r'высок\w* (?:уров|степен|качеств|производ)\w*)',
     'show a fact: number, mechanism, consequence («индекс по client_id — выборка без полного просмотра»)'),
    ('неопределённость', r'\b(некотор\w*|различн\w*|определённ\w*|определенн\w*|многие(?! ко многим)|многих(?! ко многим)|'
                         r'и т\.\s?д\.|и т\.\s?п\.|и др\.|и прочее|так или иначе|разного рода|ряд (?=\w+(?:ов|ей|ий)\b))',
     'list concretely or delete'),
    ('штамп', r'(играет (?:важную|ключевую|большую) роль|широк\w+ (?:спектр|круг)\w*|на сегодняшний день|'
              r'ни для кого не секрет|в современном мире|неотъемлем\w+ част\w+|не секрет, что|'
              r'позволяет (?:обеспечить|осуществить|реализовать))',
     'cliché: say plainly what and why'),
]
COMPILED = [(n, re.compile(rx, re.I), hint) for n, rx, hint in RULES]


def prose_lines(text: str):
    in_code = False
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith('```') or s.startswith('~~~'):
            in_code = not in_code
            continue
        if in_code or s.startswith(('@startuml', '@enduml')):
            continue
        yield i, re.sub(r'`[^`]*`', ' ', line)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--max-words', type=int, default=25, help='max sentence length in words')
    args = ap.parse_args()
    text = Path(args.file).read_text(encoding='utf-8')

    hits = []
    for ln, line in prose_lines(text):
        for name, rx, hint in COMPILED:
            for m in rx.finditer(line):
                hits.append((ln, name, m.group(0), hint))
        if line.lstrip().startswith('|'):
            continue  # table cells: no sentence length check
        for sent in re.split(r'(?<=[.!?])\s+', line):
            words = re.findall(rf'{W}+|\w+', sent)
            if len(re.findall(r'\d+', sent)) >= 3 and re.match(r'\s*(?:[-*+]|\d+[.)])\s', line):
                continue  # a list item of counts («Объём: 5 таблиц, 23 столбца, …»), not prose
            if len(words) > args.max_words:
                hits.append((ln, 'длинное предложение', f'{len(words)} words: «{sent.strip()[:60]}…»',
                             'split: one thought per sentence'))

    if not hits:
        print('No stop words found.')
        return
    by_cat = {}
    for h in hits:
        by_cat.setdefault(h[1], []).append(h)
    print(f'Places to check: {len(hits)}')
    for cat, items in by_cat.items():
        print(f'\n## {cat} ({len(items)}) — {items[0][3]}')
        for ln, _, frag, _ in items[:40]:
            print(f'  line {ln}: {frag}')
        if len(items) > 40:
            print(f'  ... and {len(items) - 40} more')


if __name__ == '__main__':
    sys.exit(main())
