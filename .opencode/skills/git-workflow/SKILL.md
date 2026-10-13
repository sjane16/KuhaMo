---
name: git-workflow
description: Use when asked to commit, push, create a Git branch, or prepare commit messages. Enforces consistent branch naming, batch-by-batch commits, verification, and explicit push authorization.
---

# Consistent Git Workflow

## Authorization

- Create commits, branches, pushes, or pull requests only when explicitly requested.
- A request for a skill describing pushes is not permission to push.
- Permission to commit does not include permission to push or create a PR.
- Never force-push, rewrite history, amend commits, skip hooks, change Git configuration, or delete branches unless explicitly authorized.
- Preserve unrelated user edits, secrets, backups, databases, and untracked files.

## Branch naming

When the user supplies a branch name, use it exactly; do not rename an existing branch for cosmetic consistency.

Otherwise use lowercase kebab-case:

`<category>/<short-purpose>`

Categories: `feature`, `fix`, `perf`, `refactor`, `chore`, `docs`.

Examples:
- `feature/report-feedback`
- `fix/live-priority-estimate`
- `perf/dashboard-latency`
- `refactor/production-consolidation`

For a new revision branch:
1. Inspect `git status --short --branch`, local/remote branches, and the requested base.
2. Confirm the remote default branch rather than assuming `main`.
3. If the user requests an updated base, fetch, switch safely, and pull with `--ff-only`.
4. Stop if switching risks user changes or the base has diverged; do not silently stash, reset, or merge.
5. Create with `git switch -c <name> <base>`; check both local and remote name collisions first.
6. Report the branch and starting commit. Do not push yet unless requested.

## Commit message standard

Use this repository's existing Conventional Commit style:

`<type>: <imperative summary>`

Allowed types:
- `feat`: new user-visible functionality
- `fix`: a bug fix
- `perf`: performance improvement
- `refactor`: consolidation without intended behavior changes
- `test`: test-only changes
- `docs`: documentation or workflow skills
- `chore`: maintenance/tooling

Keep the summary specific, in English, lowercase at the beginning, with no trailing period. Prefer 72 characters or fewer where practical. Avoid vague messages like "updates", "fixed stuff", or "final changes".

For user-requested batch/phase grouping, use a consistent suffix:
- `refactor: share notification queries and row templates (batch 2)`
- `perf: consolidate dashboard analytics (phases 5-6)`

Do not add scope parentheses before the colon in this repository. Use a body only when useful to explain a migration, compatibility decision, or verification limitation. Never claim a measured speedup or passing test without evidence.

## Batch-by-batch commits

1. Before committing inspect `git status`, `git diff`, and `git log --oneline -10`.
2. Identify which edits are task-owned versus unrelated user work. Review new files too.
3. Follow the requested grouping: one commit per batch, or per two phases if requested.
4. Keep each commit internally consistent and buildable, with its relevant tests and migrations.
5. If a file contains changes from multiple batches, split its staged hunks without modifying unrelated working-tree content. Use non-interactive staging; do not use `git add -i` or blanket `git add .`.
6. Check imports, shared definitions, and dependencies so an early batch never references code introduced only in a later batch.
7. Include regression tests in the same commit as the behavior they verify. Tests are permanent, not disposable.
8. Review `git diff --cached` and `git diff --cached --check` before every commit. Stage only explicit intended paths/hunks.
9. Run applicable checks. For this Django project use its Pipenv environment:
   - `pipenv run python manage.py check`
   - `pipenv run python manage.py test --keepdb`
   - `pipenv run python manage.py makemigrations --check --dry-run` for model/migration work
10. Never approve deletion of an existing test database automatically. Do not run seed commands against the application database for test verification.
11. If hooks fail, fix the problem and create a normal commit; do not bypass hooks or amend a failed attempt.
12. After commits, inspect status and recent hashes; confirm no intended changes were omitted and unrelated files remain untouched.

## Push procedure

Only execute when the user explicitly asks to push.

1. Inspect branch, remotes, upstream, local commits, and the diff against the remote tracking branch.
2. Review all commits being pushed for unintended files or secrets, not just the latest.
3. Fetch the target remote to establish current ahead/behind state.
4. If remote history diverged, stop and explain; do not force-push or automatically rebase.
5. First push: `git push -u origin <current-branch>`.
6. Subsequent pushes: `git push origin <current-branch>`.
7. Never push directly to the default branch unless explicitly requested.
8. Report the remote branch and resulting ahead/behind status. Creating a PR requires a separate request; use `gh` when authorized.

## Final response

Return a short table with commit hashes and batch/phase summaries, the current branch, checks actually run, remaining uncommitted paths, and whether a push occurred. Do not claim a clean worktree if unrelated edits or backups remain.
