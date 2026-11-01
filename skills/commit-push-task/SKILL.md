---
name: "commit-push-task"
description: 'Commit and push changes for an issue or ticket (commit, push, закоммить, запушь). Use Resolve: <issue> and a bullet list, preserve existing staging, omit AI attribution, and update the description of an existing MR/PR after a successful push. Find the issue in the request or branch name; ask if absent. Use for commit/push requests, including those without an issue number.'
---

# Commit & Push Task

Turn the current changes in a git repository into one clean commit tied to an issue, push it, and — if the branch already has an open merge request — bring the MR description up to date. The point is a history that a teammate can skim: the header says which issue the commit closes, a few bullets say what actually changed in human terms, and the MR description always describes what the MR currently contains, not what it contained when it was opened. The MR description uses the same layout as the commit message — `Resolve:` line, then a bullet list — so commits and MRs read the same way.

## Available tools and scope

Use this workflow in Claude Code or Codex with the tools available in the current environment. Check capabilities and authentication before using a CLI; the commands below are examples, not assumed installations.

- With a local repository and Git CLI, use Git for status, staging, diffs, commits and pushes. Identify the host and repository from its remote.
- For GitHub metadata and existing PR updates, use an available authenticated GitHub connector/API or `gh`.
- For GitLab, use an available authenticated GitLab API/connector or `glab`.
- Without a local clone, a repository API may create blobs, a tree, a commit and a branch update only if it supports reading the base and comparing the current branch head atomically (expected SHA / compare-and-swap). Scope the tree to explicitly selected files, preserve every other entry and reject concurrent changes. Never update a ref forcibly. Do not treat an API commit as a push of local staged work. If the tools cannot preserve these guarantees, report the limitation and stop before mutation.
- Preserve the established commit-and-push convention for requests invoking this workflow, including "commit". Honor explicit limits such as "commit only" or "do not push". A request to edit this skill or draft a message does not invoke its mutation workflow. Commit only changes the user authorized.

## Input

The user provides an issue identifier. Accept it in whatever form they give:

- bare number `123` → write it as `#123` (GitHub/GitLab turn `#123` into a link)
- `#123` → keep as is
- tracker key like `PROJ-123` → keep as is

If the user didn't give one, take it from the current branch name (`git branch --show-current`) — the team names branches after the task, so `PROJ-123`, `123-reset-password` or `feature/PROJ-123-reset` all carry it. Use the identifier in the same form as above and mention in the report that it came from the branch name.

If neither the message nor the branch name contains an identifier, ask for it before committing — the header is the whole reason this skill exists, so guessing would defeat it. Don't treat random numbers in the branch name (dates, versions like `v2`) as an issue; when it's unclear, ask.

## Workflow

1. **Look at the state of the repo.** Run `git status --short`, `git diff --staged` and `git diff`; inspect untracked files separately.
   - If something is already staged, preserve it and commit **only what is staged**, provided it belongs to the authorized task. Do not add or unstage anything. If staging includes secrets, unrelated changes or ambiguous ownership, stop and ask before committing.
   - If nothing is staged, review the tracked diff and each candidate untracked file, then stage only authorized task changes by explicit path (`git add -- <paths>`). For files mixing task changes and unrelated edits, stage only the relevant hunks with a supported mechanism; if the separation is ambiguous, ask before staging. Never use blanket `git add -A` or `git add .`.
   - Before committing, skim the staged file list for things that clearly don't belong in a commit: secrets (`.env`, keys, credentials), large build output, editor/OS junk. If you see any, stop and ask instead of committing them.
   - If there is nothing to commit, say so and stop.
2. **Understand the change.** Read the staged diff (and `git log -5 --oneline` for the repo's conventions). Work out what the change does as a whole, not file by file.
3. **Write the message** in the format below.
4. **Commit with exactly that message** — nothing appended. Pass the message through a file or heredoc so no tool adds trailers:
   ```bash
   git commit -F - <<'EOF'
   Resolve: #123

   * Added ...
   * Removed ...
   EOF
   ```
   Do not mention AI, model/provider names or assistant identities in commit messages or MR/PR titles and descriptions; add no co-author or generated-by trailers, emoji, or signatures. The commit should look like the user wrote it.
5. **Push right away** — this workflow includes publication; continue without another confirmation unless the user explicitly requested a local commit only or forbade pushing. In that case report the commit without pushing or updating a remote MR/PR.
   - If the current branch has an upstream: `git push`.
   - If it has no upstream yet: `git push -u origin <current-branch>`.
   - If the repo has no remote at all, keep the commit, say the push was skipped and why.
   - If the push is rejected (remote has newer commits, protected branch, auth error), stop and report the error. **Never force-push** and don't pull/rebase on your own — that can overwrite or tangle other people's work, so the user decides how to reconcile.
6. **Update the open MR description, if there is one.** See [Updating the MR description](#updating-the-mr-description). Do this only after a successful push — before that, the MR doesn't contain the new commit yet.
7. **Report back** with the short hash, the message (e.g. via `git log -1 --format='%h%n%n%B'`), where it was pushed (branch and remote) or why it wasn't, and what happened to the MR: its link and the updated description, or that there is no open MR for this branch.

## Message format

```
Resolve: <issue>

* <change>
* <change>
* <change>
```

- First line is exactly `Resolve: <issue>` — nothing else on it.
- One blank line, then bullets starting with `* `.
- Usually 2–5 bullets. One bullet is fine for a tiny change; more than ~7 means you are listing files instead of describing changes — group them.
- Language: write the bullets in the language the repo's recent commit messages use; if there is no history or it is mixed, use English.

## Writing good bullets

Each bullet starts with a past-tense verb and says what changed from a reader's point of view:

- **Added** — new feature, endpoint, field, test, config
- **Removed** — deleted code, feature, dependency
- **Fixed** — a bug, with the symptom if it fits in a few words
- **Changed / Updated / Renamed / Moved** — behavior or structure changes

Aim for the level of detail a reviewer needs: what and, when it's not obvious, why. Skip mechanics nobody cares about (import reordering, formatting) unless that is the whole commit. Keep each bullet to one line.

## Updating the MR description

Reviewers read the MR description, not individual commits. When a branch gets new commits after the MR was opened, the description quietly goes stale — it still describes the first version of the work. This step keeps it honest, and keeps it in the same shape as the commits: an issue line and a list of changes, never a paragraph of prose.

### Find the MR

Look for an **open** MR whose source branch is the current branch:

- **GitLab** (`glab`): `glab mr list --source-branch <branch>` (lists open MRs by default), then `glab mr view <iid> -F json` for its `description`, `target_branch` and `web_url`.
- **GitHub** (`gh`): `gh pr list --head <branch> --state open --json number,body,baseRefName,url`.

Use whichever matches the remote (`git remote get-url origin`), or the corresponding connector/API. For API lookup, match repository, source branch, source owner (including forks), open state and target branch; do not update a same-named branch in another repository.

- No open MR → skip this step and just mention it in the report. **Don't create an MR** — opening one is the user's decision (title, reviewers, target branch).
- Neither an authenticated CLI nor a capable connector/API is available → don't fail the whole run: the commit and push already succeeded. Say the MR wasn't updated and why, and give the user the updated description text (in the format below) so they can paste it in.
- Several open MRs from the same branch (rare) → ask which one to update.

### Description format

The part of the description that says what the MR changes always has exactly the commit layout:

```
Resolve: <issue>

* <change>
* <change>
* <change>

<other sections of the description, unchanged>
```

- First line `Resolve: <issue>`, then one blank line, then the bullets. The blank line matters: without it GitLab/GitHub markdown glues the list to the line above.
- Every bullet on its own line, starting with `* `, one line each. Never join bullets into a sentence or a paragraph, never write the changes as prose.
- Same bullet rules as commits ([Writing good bullets](#writing-good-bullets)): past-tense verb, behavior not files, roughly 2–7 bullets for the whole MR.
- No extra heading or intro sentence above the list ("This MR adds…", "## Summary") — the `Resolve:` line is the header, like in the commit.
- If the project's MR template already has its own section for changes (e.g. `## Changes`, `## Что сделано`), put the list under that heading instead, and keep the `Resolve:` line at the very top unless the issue is already referenced elsewhere in the template.
- After the list, one blank line, then the rest of the description.

### Rewrite the change list from the whole MR

The description should describe the MR as a whole — everything it changes relative to the target branch — not be a log of commits. So don't just append the new commit's bullets to the bottom. Instead:

1. Read the current description, and the MR's full contents: `git fetch origin <target>` then `git log --format='%h %B' origin/<target>..HEAD` and `git diff --stat origin/<target>...HEAD` (look at the diff itself where the stat isn't enough).
2. Split the current description into two parts:
   - **The change part** — anything that says what the MR does: an existing bullet list, or paragraphs of prose describing the work (written by a person or by an earlier run), or a mix of both.
   - **Everything else** — things only a human could write: a "how to test" section, checklists (with their ticked state), screenshots, links, notes for reviewers, template sections that aren't about the changes.
3. **Rebuild the change part as a list** that matches what the MR does **now**:
   - Start from what the change part already says. If it is prose, turn each statement about a change into a bullet; if two sentences describe the same change, merge them into one bullet. Don't lose facts — a detail from the prose (a limit, a reason, a name) goes into the matching bullet. A short "why" fits at the end of a bullet; a longer note that isn't a change (motivation, caveat for reviewers) stays as a short paragraph after the list, not instead of it.
   - New things from this commit → add bullets.
   - This commit changes something the MR already added (renamed it, changed its behavior) → update that bullet instead of adding a second one.
   - This commit fixes a bug in code introduced by the same MR → usually no new bullet. From the reviewer's point of view the feature was never broken on the target branch; "Fixed X" would describe a bug that doesn't exist there. Adjust the original bullet if the fix changes what it says.
   - This commit reverts or removes something the MR added earlier → drop that bullet.
   - Check the result against the full MR diff from step 1, not only against the old description: every meaningful change in the diff is covered by a bullet, and every bullet is still true.
4. **Keep everything else exactly as it is** — byte-for-byte, in its original order, after the list. Ticked checkboxes stay ticked, screenshots and links stay where they were.
5. Keep the description's existing language for the bullets. If the description is empty or has no language to follow, use the commit language rules above. If the description has no issue reference at all, add the `Resolve: <issue>` line at the top.
6. If the description is **already in this format** and the commit adds nothing to it (a tiny tweak already covered by an existing bullet), leave it alone and say so in the report — don't touch it just to touch it. A description that is still prose, or a list without the `Resolve:` header, is not in the format yet, so it does get rewritten.

Change only the description. Title, labels, assignees, reviewers and draft status are the user's to manage.

### Write it back

Write the new description to a file and pass the file — never put the description inline in the command with `\n` escapes, which arrive as literal `\n` and turn the list into one line. Nothing gets appended: no AI attribution, no generated-by text, no signature, same as the commit.

- **GitLab:** use the API/connector with the description as a structured string; if using `glab`, check `glab mr update --help` and pass the file contents as one literal argument through a process API, never interpolated shell code.
- **GitHub:** `gh pr edit <number> --body-file /path/to/description.md`

Fetch the description right before writing. Compare it with the version used to prepare the edit; if it changed, rebuild from the latest description. Use conditional updates where supported; otherwise reread immediately before mutation and report that the API does not guarantee atomic description updates. Never overwrite a detected concurrent edit. With an API/connector, send the exact multiline text as a structured field.

After writing, read the description back (`glab mr view <iid> -F json` / `gh pr view <number> --json body`) and check that it matches the file: the `Resolve:` line, the blank line, and each bullet on its own line. If it came out mangled, fix it and write it again.

## Examples

Diff adds a password-reset endpoint, an email template, and tests; removes an unused helper.

```
Resolve: #214

* Added POST /auth/reset-password endpoint with token expiry
* Added password reset email template
* Added tests for reset flow and expired tokens
* Removed unused legacy hashPassword helper
```

Diff fixes an off-by-one in pagination and bumps a dependency.

```
Resolve: SHOP-88

* Fixed last item missing on paginated product lists
* Updated axios to 1.7.4
```

Bad — lists files and says nothing about behavior:

```
Resolve: #214

* Changed auth.ts
* Changed reset.html
* Changed auth.test.ts
```

### MR description update

The MR for #214 is open with this description:

```
Resolve: #214

* Added POST /auth/reset-password endpoint
* Added password reset email template

## How to test
- [x] Request reset for an existing user
- [ ] Check the email in Mailpit
```

The new commit adds a 30-minute token expiry, fixes the template's broken link (the template came in with this same MR), and adds tests. Updated description:

```
Resolve: #214

* Added POST /auth/reset-password endpoint with 30-minute token expiry
* Added password reset email template
* Added tests for reset flow and expired tokens

## How to test
- [x] Request reset for an existing user
- [ ] Check the email in Mailpit
```

The endpoint bullet absorbed the expiry, the template fix produced no "Fixed" bullet, the tests got a new bullet, and the "How to test" section with its ticked box is untouched.

### MR description written as prose

The MR for SHOP-88 has this description:

```
В этом MR исправлена пагинация в каталоге: на последней странице пропадал последний товар. Заодно обновил axios до 1.7.4, потому что в старой версии была уязвимость.

## Как проверить
- [ ] Открыть каталог, перейти на последнюю страницу
```

The new commit adds a page-size selector. Updated description:

```
Resolve: SHOP-88

* Исправлен пропадающий последний товар на последней странице каталога
* Обновлён axios до 1.7.4 из-за уязвимости в старой версии
* Добавлен выбор количества товаров на странице

## Как проверить
- [ ] Открыть каталог, перейти на последнюю страницу
```

The prose became bullets in the same language, with nothing lost (the reason for the axios update moved into its bullet), the `Resolve:` line was added at the top, the new commit got its own bullet, and the "Как проверить" section is untouched.

Bad — the same changes written back as prose, or glued into one line:

```
Resolve: SHOP-88 В этом MR исправлена пагинация, обновлён axios и добавлен выбор количества товаров на странице.
```