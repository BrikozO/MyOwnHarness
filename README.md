# MyOwnHarness

Единый набор Agent Skills для Claude Code и OpenAI Codex: документация баз данных, создание и правка диаграмм, коммиты по задачам и подготовка релизов. Репозиторий служит плагином и маркетплейсом. Общие инструкции хранятся в одном каталоге `skills/`; платформозависимые расширения устанавливаются отдельно.

## Совместимость

| Компонент | Claude Code | Codex | Назначение |
|---|---|---|---|
| [`write-db-doc`](skills/write-db-doc/SKILL.md) | Да | Да | Описание БД на русском по ГОСТ, словарь данных и ER-диаграмма из DDL |
| [`draw-diagrams`](skills/draw-diagrams/SKILL.md) | Да | Да | Создание и правка Use Case, Activity и Sequence; практики и антипаттерны, Mermaid и PlantUML |
| [`commit-push-task`](skills/commit-push-task/SKILL.md) | Да | Да | Коммит `Resolve: #N` со списком изменений, push и обновление существующего MR/PR |
| [`release-tag`](skills/release-tag/SKILL.md) | Да | Да | Анализ изменений, SemVer, проверка OpenAPI, русские release notes; публикация только по запросу на реальный релиз |
| [`mtuci-design-system`](design-systems/mtuci-design-system/README.md) | Ресурсы | Ресурсы | Общие токены, шрифты, компоненты и изображения для презентаций МТУСИ |
| [`lofi-plan`](platforms/claude/lofi-plan/README.md) | Отдельный мод | Нет | Прогресс формирования и выполнения плана под полем ввода |
| [`lofi-usage`](platforms/claude/lofi-usage/README.md) | Отдельный мод | Нет | Контекст и лимиты 5h/7d над полем ввода |

Скиллы выбирают доступные инструменты среды. Для локальной работы с Git нужен Git CLI; удалённые операции возможны через поддерживаемые API/коннекторы либо аутентифицированные `gh`/`glab`. Для скриптов `write-db-doc` нужен Python 3.8+; парсинг, SVG и проверки используют стандартную библиотеку. PNG дополнительно требует CairoSVG или `rsvg-convert`. При недоступной операции скилл сообщает об ограничении.

Дизайн-система не устанавливается как скилл: используйте файлы из `design-systems/` по ссылкам. Источник оформления — [артефакт Design System](https://claude.ai/artifact/33g7qF5udKMJkMVT78orbv).

## Структура

```text
MyOwnHarness/
├── plugin.json                    # переносимый Agent Plugins 1.0.0
├── .claude-plugin/
│   ├── plugin.json                # совместимость с Claude Code
│   └── marketplace.json           # три независимых пакета
├── skills/
│   ├── commit-push-task/SKILL.md
│   ├── draw-diagrams/
│   │   ├── SKILL.md
│   │   ├── agents/openai.yaml
│   │   └── references/
│   ├── release-tag/SKILL.md
│   └── write-db-doc/
│       ├── SKILL.md
│       ├── references/
│       ├── scripts/
│       └── tests/
│           └── fixtures/
├── design-systems/
│   └── mtuci-design-system/
│       ├── README.md
│       ├── design-system.json
│       ├── tokens.json
│       ├── tokens.css
│       ├── components/
│       ├── assets/
│       └── fonts/
├── platforms/
│   └── claude/
│       ├── lofi-plan/
│       └── lofi-usage/
└── README.md
```

Корневой `plugin.json` следует [спецификации Agent Plugins](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json). Общие скиллы обнаруживаются в стандартном `skills/` без поля `skills` в переносимом манифесте. `.claude-plugin/plugin.json` сохраняет метаданные для Claude Code. Имя обоих манифестов — `my-own-harness`, версия — `0.1.0`; при выпуске новой версии их нужно обновлять согласованно. Корневой плагин не объявляет зависимости от модов, MCP-серверы или хуки. Вложенные пакеты в `platforms/` не являются его компонентами.

## Установка основных скиллов в Claude Code

В интерактивной сессии Claude Code:

```text
/plugin marketplace add BrikozO/MyOwnHarness
/plugin install my-own-harness@my-own-harness
```

Устанавливается только основной плагин с четырьмя общими скиллами. Например, явный вызов скилла: `/my-own-harness:write-db-doc`. Для приватного репозитория требуется доступ к GitHub.

Для локальной проверки изменений без публикации:

```bash
claude plugin validate /absolute/path/to/MyOwnHarness
claude --plugin-dir /absolute/path/to/MyOwnHarness
```

Команды и правила размещения компонентов описаны в [документации маркетплейсов](https://code.claude.com/docs/en/plugin-marketplaces) и [манифеста Claude Code](https://code.claude.com/docs/en/plugins-reference).

## Установка основных скиллов в Codex

В Codex CLI откройте `/plugins`, добавьте источник `BrikozO/MyOwnHarness` и установите только `my-own-harness`. Запустите новую сессию после установки. Если установленная версия CLI поддерживает подкоманду `plugin`, эквивалентные команды в терминале:

```bash
codex plugin marketplace add BrikozO/MyOwnHarness
codex plugin add my-own-harness@my-own-harness
```

Проверьте наличие команд через `codex plugin --help`. Для разработки вместо GitHub можно добавить локальный checkout командой `codex plugin marketplace add /absolute/path/to/MyOwnHarness` в отдельном тестовом окружении. В каталоге маркетплейса видны и Claude-моды — их не нужно устанавливать в Codex. Установка основного пакета не устанавливает их автоматически.

Если ваша версия не поддерживает установку плагинов из такого источника, используйте поддерживаемое [обнаружение локальных скиллов](https://learn.chatgpt.com/docs/build-skills). На macOS/Linux создайте ссылки на четыре папки скиллов в `~/.agents/skills/`:

```bash
git clone https://github.com/BrikozO/MyOwnHarness.git
cd MyOwnHarness
mkdir -p "$HOME/.agents/skills"
for skill in commit-push-task draw-diagrams release-tag write-db-doc; do
  if [ -e "$HOME/.agents/skills/$skill" ] || [ -L "$HOME/.agents/skills/$skill" ]; then
    echo "Уже существует: $HOME/.agents/skills/$skill — оставлен без изменений"
  else
    ln -s "$PWD/skills/$skill" "$HOME/.agents/skills/$skill"
  fi
done
```

Checkout должен оставаться на месте: ссылки используют его содержимое без копирования. Для установки только в один проект аналогично используйте `<project>/.agents/skills/`. На Windows используйте поддерживаемую файловую ссылку или установщик скиллов вашей среды. Не устанавливайте одновременно плагин и отдельные копии тех же скиллов: это создаёт дубликаты в списке.

Проверьте четыре имени через `/skills`; явный вызов в CLI — `$write-db-doc`, `$draw-diagrams`, `$commit-push-task` или `$release-tag`. Если изменения не появились, перезапустите Codex. См. [установку плагинов](https://learn.chatgpt.com/docs/plugins) и [переносимую упаковку](https://developers.openai.com/plugins/build/plugins).

## Дополнительные моды для Claude Code

Устанавливайте каждый мод только если он вам нужен. В Claude Code, после регистрации маркетплейса:

```text
/plugin install lofi-plan@my-own-harness
```

Для полосы использования — отдельная установка:

```text
/plugin install lofi-usage@my-own-harness
```

Это UI-модули Claude Code с импортами `claude-code`, собственными хуками и типами. Они требуют версии Claude Code с поддержкой модов. Их `hooks/`, `types/`, тесты и локальные импорты сохраняются внутри каждого пакета. После обновления используйте `/reload-plugins` согласно README мода. В основной плагин их хуки не включены.

Если моды ранее импортировались в Codex, удалите именно эти два пакета через `/plugins`. В версиях CLI с `plugin remove`:

```bash
codex plugin remove lofi-plan@my-own-harness
codex plugin remove lofi-usage@my-own-harness
```

После этого начните новую сессию. Не удаляйте маркетплейс или основной `my-own-harness`: они нужны общим скиллам. Если удаление запрещено правами файловой системы, выполните эти команды в обычном терминале с доступом к своему профилю. Наличие исходников модов во вложенном каталоге кэша основного пакета само по себе не означает, что моды установлены или подключены.

## Диаграммы: создание и правка

`draw-diagrams` строит новые схемы и точечно обновляет существующие по требованиям, коду и API-контрактам. Основные нотации — UML Use Case, Activity и Sequence, исходники — Mermaid и PlantUML. Скилл выбирает тип схемы под вопрос и аудиторию, проверяет альтернативы и ошибки, сохраняет ID и незатронутые части при правках. Для C4, BPMN и ER он помогает выбрать модель и применить профильные правила.

Примеры запросов:

- «Используй `$draw-diagrams`: создай Activity обработки заявки с параллельными проверками и ветками отказа».
- «Используй `$draw-diagrams`: обнови существующую Sequence по изменённому API, сохрани алиасы и комментарии».
- В Claude Code явный вызов — `/my-own-harness:draw-diagrams`.

Практики и антипаттерны основаны на лекции Ани Гуреевой «Моделирование и диаграммы» (Центральный университет, неделя 5); [конспект с номерами слайдов](skills/draw-diagrams/references/lecture-practices.md) включён в скилл. Редактируемый исходник обязателен; рендер и визуальная проверка выполняются доступными инструментами, а ограничения указываются явно.

## Добавление универсального скилла

1. Создайте `skills/<skill-name>/SKILL.md` с YAML frontmatter `name` и `description`. Имя должно совпадать с каталогом, содержать строчные латинские буквы, цифры и одиночные дефисы; описание — не более 1024 символов. См. [Agent Skills](https://agentskills.io/specification).
2. Пишите общие инструкции без зависимости от исполнителя, модели или провайдера. Проверяйте наличие инструментов, указывайте ограничения и используйте относительные пути к ресурсам скилла.
3. Добавляйте `references/`, `scripts/` и `assets/` только при необходимости. Тесты и их исходные данные храните вместе со скиллом; не ссылайтесь на личные каталоги или отсутствующие evals.
4. Обновите таблицу совместимости и проверьте обнаружение скилла обеими платформами. Стандартный `skills/` не требует отдельной регистрации каждого скилла в манифесте.
5. Версию меняйте только в рамках отдельного согласованного выпуска, согласованно в обоих манифестах.

Платформозависимые расширения помещайте в `platforms/<platform>/<component>/` с собственным манифестом и явной отдельной установкой. Общие скиллы и дизайн-ресурсы туда не копируются. Каталог для новой платформы создавайте только при появлении реального компонента; сейчас специфичных расширений Codex нет.

## Проверка

Из корня репозитория:

```bash
python3 -m unittest discover -s skills/write-db-doc/tests -v
git diff --check
```

Регрессионные тесты проверяют PostgreSQL, MySQL, итоговое состояние миграций, связи и разметку SVG, полноту описания и стиль. Тестовые DDL находятся в `skills/write-db-doc/tests/fixtures/`; PNG-конвертер для этих проверок не обязателен. Бизнес-логика парсера не требует зависимостей Python вне стандартной библиотеки.

Дополнительно проверьте JSON-манифесты, пути `source` в маркетплейсе, относительные ссылки и обнаружение четырёх скиллов. Для Claude используйте `claude plugin validate` и сессию с `--plugin-dir`; UI-тесты модов импортируют `claude-code/testing` и требуют соответствующего окружения Claude Code. Для Codex проверьте `/skills` и отсутствие установленных lofi-модов в `/plugins`. Статическая проверка манифестов не заменяет проверку интерфейса в установленном клиенте.
