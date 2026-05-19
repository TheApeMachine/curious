GIT_POLICY_SECTION = """## Git policy (binding — all agents)

You may **read** repository state and history only. **Never** run git (or any shell command) that changes refs, the index, or the working tree — including undoing or discarding uncommitted work.

The **human** commits; agents deliver changes in the **working tree**. Reviewers judge `git diff` and files on disk — not whether `HEAD` includes the fix.

### Allowed (read-only)

`git status`, `git diff`, `git log`, `git show`, `git branch` (list only), `git rev-parse`, `git describe`, `git ls-files`, `git blame`, `git shortlog`, `git diff-tree`, `git cat-file`

### Forbidden (never run — stop and report if tempted)

- **Discard / undo work:** `git reset`, `git restore`, `git checkout` / `git switch` when it would move HEAD or drop local changes, `git clean`, `git stash` / `git stash pop` / `git stash drop`
- **History / refs:** `git revert`, `git rebase`, `git cherry-pick`, `git merge`, `git pull`, `git push`, `git commit`, `git add`, `git am`
- **Worktrees / branch games:** `git worktree`, checking out other branches to “sync” deliverables — stay on the current branch; edit files in place
- **Destructive:** removing or rewriting `.git`, force-push, or aliases/scripts that perform the above

Inspect changes with `git status` / `git diff` / `git log` only. To fix files, use editor tools — **not** git reset/restore/checkout."""

GIT_POLICY_SUBAGENT = (
    "Git: read-only only. Human commits; judge working tree. No reset/restore/commit/add/worktree."
)

GIT_POLICY_SPEC_CONSTRAINT = (
    "Human commits only; agents use read-only git (status, diff, log) and must not "
    "reset, restore, commit, or use worktrees."
)
