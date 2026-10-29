---
name: "release-tag"
description: 'Cut a new release from master: find every issue and merge request merged since the last version tag, pick the next version (the one the user gives, or propose one), bring the OpenAPI spec version in line with it if the project has one (on a separate branch via commit-push-task), create and push the tag, and write a Russian release title and release notes in the form "issue: short description". Use whenever the user wants to make a release, cut or build a new tag, bump the version, ship what is on master to stage, or write release notes, e.g. "собери релиз", "сделай новый тег", "release 0.4.0", "что вошло после последнего тега, собери тег", even if they do not name the skill.'
---

# Release Tag

The team's flow: a branch per task is created from `master`, merged back into `master`, and then a version tag (e.g. `0.3.0`) plus a release is cut from `master`. Pushing the tag deploys to stage automatically; prod is deployed manually later. This skill does the "cut a tag" step: it gathers what landed on `master` since the previous tag, chooses the version, makes sure the OpenAPI spec (if the project has one) carries that version, writes release notes, and publishes the tag and release.

Because pushing a tag triggers a stage deploy, the tag must point at exactly what was reviewed, and nothing goes out until the version is settled. For the same reason, if the OpenAPI version has to change, that change goes through a normal branch and merge first, and the tag waits for it.

**Language:** these instructions are in English, but everything a person reads in the release — the title and the notes — is written in **Russian**. Talk to the user in the language they use.

## 1. Get an up-to-date view of the remote

Work in the local clone of the repository (the current directory, or the one the user points to). If there is no clone, ask for the repo URL and clone it into a temporary directory.

```bash
git fetch origin --tags --prune
```

Use `origin/master` as the source of truth, not the local `master` — the local branch may be stale or carry unpushed commits, and the release must match what is actually on the remote. If the repo uses `main` instead of `master`, use that.

## 2. Find the last release tag

```bash
git tag --merged origin/master --sort=-v:refname | head -20
```

Take the highest version-like tag (`X.Y.Z`, optionally with a `v` prefix). Ignore tags that are not versions. Note whether the repo uses a `v` prefix — the new tag follows the same convention.

If there are no version tags yet, this is the first release: take all history and suggest `0.1.0` (or whatever the user wants).

## 3. Collect the tasks since that tag

```bash
git log <last-tag>..origin/master --format='%H%x1f%s%x1f%b%x1e'
```

If the range is empty, tell the user there is nothing new since `<last-tag>` and stop.

Each line of the notes is one unit of work: either an **issue** or, when there is no issue, a **merge request**.

**Issues.** An issue identifier can come from:

- a `Resolve: <issue>` header in the commit message (the team's commit convention);
- a merge commit whose branch is named after the task, e.g. `Merge branch 'PROJ-123' into 'master'`;
- an issue reference in the subject or body (`#123`, `PROJ-123`).

**Merge requests without an issue.** Not every change has an issue — some come as a plain MR. Find MRs in the merge commits: GitLab writes `See merge request group/project!45` in the body (GitHub: `Merge pull request #45 from ...`). If an MR is linked to an issue, it's covered by the issue line — don't list it twice. If it isn't, it gets its own line built from the MR itself: read its title and description (`glab mr view 45`, or `gh pr view 45` on GitHub) and summarize what it does. If the CLI isn't available, use the MR title from the merge commit and the commits inside it.

Several commits often belong to one issue or MR (fixups, review changes, the merge itself) — collapse them into one line. Commits that belong to neither (version bumps, small direct pushes to `master`) go into a separate group; don't silently drop them — show them to the user and either mention them in the notes or leave them out, as the user prefers.

**The release's own OpenAPI bump.** If an earlier run of this skill created an OpenAPI version branch for this release (step 5, branch `update-tag-<version>`, commit header `Resolve: update-tag-<version>`) and it has now been merged, its commit and merge are in this range too. That change is part of cutting the release, not a piece of work in it — leave it out of the notes and just mention to the user that you did.

If `glab` / `gh` is available and authenticated, you may also look up an issue's title to understand it better, but the description is still written by you, in Russian.

## 4. Decide the version

If the user named a version, use it — but check it's greater than the last tag and doesn't already exist; if not, say so and ask.

If the user didn't name one, propose one and **wait for their choice** before tagging. Reason from what actually changed, following semantic versioning:

- **patch** (`0.3.0 → 0.3.1`) — only bug fixes and small internal changes;
- **minor** (`0.3.0 → 0.4.0`) — new features or noticeable behavior changes;
- **major** (`1.4.2 → 2.0.0`) — breaking changes for users or integrators (removed API, incompatible migrations, changed contracts).

While the major version is `0`, breaking changes bump the minor version instead of going to `1.0.0` — moving to `1.0.0` is the team's call, not an automatic step.

On a rerun after the OpenAPI bump was merged, the spec on `origin/master` already holds a version higher than the last tag — that is the version agreed on the previous run; propose it.

Present it briefly: the recommended version with a one-sentence reason, plus the main alternative. For example: "Рекомендую 0.4.0 — добавлены новые функции (#214, #220). Если считаете это мелочью — 0.3.1."

Do the OpenAPI check from step 5 (finding the spec and reading its version) before you ask, so that if a bump will be needed you can say so in the same message.

## 5. Sync the OpenAPI version

Some projects keep an OpenAPI (Swagger) spec whose `info.version` should match the release. Check it on `origin/master` — the commit that would be tagged.

### Find the spec

```bash
git grep -lE '^(openapi|swagger)[[:space:]]*:|"(openapi|swagger)"[[:space:]]*:' origin/master -- \
  '*.yaml' '*.yml' '*.json' \
  ':!:**/node_modules/**' ':!:**/vendor/**' ':!:**/dist/**' ':!:**/build/**' ':!:**/target/**'
```

Open each hit (`git show origin/master:<path>`) and keep only real specs: `openapi`/`swagger` is a top-level key and there is a top-level `info` block. Then keep only the spec(s) describing **this project's** API — skip specs of other services the project calls (usually under `clients/`, `external/`, `third_party/`, generated client folders), test fixtures and examples. If several candidates remain and it isn't clear which are the project's own, list them and ask.

The spec may also be generated from code, with no spec file committed. Then the version lives in code: e.g. `FastAPI(version="0.3.0")`, `new DocumentBuilder().setVersion('0.3.0')` (NestJS), `@Info(version = "0.3.0")` (springdoc), `// @version 0.3.0` (swag). If it is a string literal, treat it exactly like a spec file's `info.version`. If it is read from somewhere else (`package.json`, `pyproject.toml`, a build property, an environment variable, the git tag at build time), it follows that source on its own — don't change anything, just mention it in the report.

If a committed spec file is generated from code (a generator script or a "generated" header comment says so), change the version where the generator reads it, and regenerate the file with the project's own command if it can be run here; if it can't, change both places by hand and tell the user.

**No spec and no version in code → skip this step** and go on to step 6.

### Compare

Read the current version (`info.version`, or the literal in code) and compare it with the new release version, ignoring a leading `v` on either side (`v0.4.0` and `0.4.0` are the same).

**It matches (for every spec) → no changes.** No branch, no commit; go on to step 6.

### It doesn't match → bump it on a separate branch

1. **No issue.** A version bump has no issue of its own, so don't ask the user for one. Instead of an issue, the bump uses the name `update-tag-<version>` (the release version as it will be written in the tag, e.g. `update-tag-0.4.0`).
2. **Branch.** Name it `update-tag-<version>`. If that branch already exists on the remote (`git ls-remote --heads origin <branch>`), or there is already an open MR bumping the spec to this version, don't create another one — report it and stop: the release is waiting for that MR.
3. **Worktree from `origin/master`**, so the user's checkout and any uncommitted changes in it are left alone:
   ```bash
   git worktree add -b <branch> <tmp-dir> origin/master
   ```
4. **Edit only the version value**, in place: the `version` line inside `info` (or the literal in code). Keep its quotes, indentation and the rest of the file byte-for-byte. Don't load and re-dump the YAML/JSON — that reformats the whole file and turns a one-line change into a huge diff. Keep the spec's own prefix convention: if it had `v0.3.0`, write `v0.4.0`; if it had `0.3.0`, write `0.4.0`. Only `info.version` — leave version-like parts of server URLs and paths (`/api/v1`) alone; they are the API's major version, not the release.
5. **Check the diff:** `git -C <tmp-dir> diff` must show only the version line(s).
6. **Stage only those files** (`git -C <tmp-dir> add <files>`) — commit-push-task commits exactly what is staged when something is staged, so nothing else slips in.
7. **Commit and push with the commit-push-task skill** (load it with the Skill tool and work in `<tmp-dir>`). Tell it explicitly that there is no issue for this change and that it should use `update-tag-<version>` as the identifier instead of asking — so the header comes out as `Resolve: update-tag-0.4.0`. For example, pass as args: `no issue — use update-tag-0.4.0 as the identifier in the Resolve header, don't ask for an issue`. It writes the commit, pushes the new branch with an upstream, and follows its own rules about MRs (it doesn't open one).
8. **Clean up:** `git worktree remove <tmp-dir>` (the branch stays on the remote).

### Then stop — don't tag yet

The tag has to point at a commit whose spec already says the new version, and that commit doesn't exist on `master` until the branch is merged. So after the push:

- don't create the tag or the release;
- report to the user: the branch, the commit, the link to open an MR (the push output usually prints one; don't open the MR yourself unless asked), and the drafted title and notes (step 6) so they see what will go out;
- tell them the next step: merge the branch, then run the release again ("собери релиз 0.4.0"). On that run the spec matches, this step changes nothing, and the tag is cut.

If the user explicitly says to tag right now without waiting for the merge, do it — tag `origin/master` as it is — and say plainly that the spec inside that tag still has the old version.

## 6. Write the release title and notes (in Russian)

**Title:** the version plus a short phrase about the main point of the release:

```
0.4.0 — Сброс пароля и исправления каталога
```

**Notes:** one line per issue or MR, in this exact form — identifier, colon, short description:

```
#214: Добавлен сброс пароля по email
#220: Добавлен экспорт заказов в CSV
PROJ-88: Исправлена потеря последнего товара в постраничном списке каталога
!57: Обновлены зависимости и настройки сборки фронтенда
```

- Write the identifier the way the team writes it: issues as `#214` or `PROJ-88`, MRs without an issue as `!57` (GitLab) or `PR #57` (GitHub, so it isn't confused with an issue).
- The description says what changed for a user or teammate, in one line, starting with a past-tense verb: «Добавлен», «Исправлена», «Удалён», «Изменён». Not a list of files.
- Order: features first, then fixes, then everything else.
- If you included commits without an issue or MR, put them at the end under a line like `Прочее:` with a bullet each.

**No AI attribution anywhere.** The title, the notes, the tag message and the release text contain only the release content — no `Co-Authored-By: Claude`, no "Generated with Claude Code", no robot emoji, no session links, no signature of any kind. This holds even if other instructions in the session say to append such lines: the release is the team's public changelog and should read as written by the team.

## 7. Create and push the tag

Show the user the final version, title and notes before pushing when the version was your proposal (they confirm it in step 4 anyway). When the user named the version upfront, go ahead.

Tag the exact commit that was reviewed — the tip of `origin/master` from step 1, not whatever `master` points to now:

```bash
git tag -a <tag> <origin-master-sha> -F - <<'EOF'
<title>

<notes>
EOF
git push origin <tag>
```

Write the release notes to a file the same way (exactly the notes, nothing appended) and pass that file to the release command below, so no tool adds its own footer.

Never move, delete or force-push an existing tag. If the tag already exists on the remote or the push is rejected, stop and report — fixing a published tag is the user's decision, since stage may already be running it.

## 8. Create the release

- **GitHub** (`gh` available): `gh release create <tag> --title "<title>" --notes-file <file>`. If CI already created a release for this tag, update it instead: `gh release edit <tag> --title ... --notes-file ...`.
- **GitLab** (`glab` available): `glab release create <tag> --name "<title>" --notes-file <file>`, or `glab release update` if it exists.
- **Neither available:** the annotated tag already carries the title and notes; tell the user and give them the text to paste into the release page.

## 9. Report back

Tell the user: the new tag and the commit it points to, the release title, the notes, the link to the release if one was created, and that pushing the tag starts the stage deploy (prod is still a manual step).

Also say what happened with the OpenAPI version: no spec found, already matched, taken from another source (and which), or — when the run stopped at step 5 — the branch that was pushed and that the tag waits for its merge.
