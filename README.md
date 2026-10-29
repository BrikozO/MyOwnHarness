# MyOwnHarness

Мой репозиторий со скиллами и обвязкой для Claude Code. Репо — это одновременно плагин и маркетплейс.

## Скиллы

| Скилл | Что делает |
|---|---|
| [`write-db-doc`](skills/write-db-doc/SKILL.md) | Описание БД по ГОСТ Р 59795-2021 / ГОСТ 34: словарь данных, связи, ER-диаграмма из DDL |
| [`commit-push-task`](skills/commit-push-task/SKILL.md) | Коммит и пуш по задаче (`Resolve: #N` + список изменений), обновление описания MR |
| [`release-tag`](skills/release-tag/SKILL.md) | Сборка релиза из `master`: следующая версия, версия OpenAPI, тег и release notes на русском |

## Дизайн-системы

| Система | Для чего |
|---|---|
| [`mtuci-design-system`](design-systems/mtuci-design-system/README.md) | Презентации к занятиям курсов МТУСИ: слайд 1920×1080, токены, шрифты, компоненты слайдов |

Источник — артефакт Design System в claude.ai: https://claude.ai/artifact/33g7qF5udKMJkMVT78orbv.

## Моды

Отдельные плагины с хуками и UI поверх интерфейса Claude Code. Ставятся независимо от скиллов.

| Мод | Что делает |
|---|---|
| [`lofi-plan`](mods/lofi-plan/README.md) | Прогресс-бар под полем ввода: этапы формирования плана, затем выполненные шаги |
| [`lofi-usage`](mods/lofi-usage/README.md) | Полоса над полем ввода: заполнение контекста и лимиты 5h/7d со временем до сброса |

## Структура

```
.claude-plugin/
  plugin.json        # манифест плагина со скиллами
  marketplace.json   # манифест маркетплейса: скиллы (корень репо) и моды
skills/
  <skill-name>/SKILL.md
design-systems/
  <system-name>/     # README, tokens.css/json, fonts, components
mods/
  <mod-name>/        # .claude-plugin/plugin.json, hooks/, types/
```

## Установка в Claude Code

```
/plugin marketplace add BrikozO/MyOwnHarness
/plugin install my-own-harness@my-own-harness
/plugin install lofi-plan@my-own-harness
/plugin install lofi-usage@my-own-harness
```

## Скиллы в claude.ai

Каждую папку из `skills/` можно запаковать в ZIP и загрузить в Settings → Capabilities → Skills.

## Добавить новый скилл

1. Создать `skills/<name>/SKILL.md` с frontmatter `name` и `description`.
2. Поднять `version` в `.claude-plugin/plugin.json`.
