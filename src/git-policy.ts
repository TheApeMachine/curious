/**
 * Binding git rules for every Curious agent (main loop, subagents, bootstrap, roadmap).
 * Prompt-level only — the Cursor SDK does not expose shell command denylists.
 */
export const GIT_POLICY_SECTION = `## Git policy (binding — all agents)

You may **read** repository state and history only. **Never** run git (or any shell command) that changes refs, the index, or the working tree — including undoing or discarding uncommitted work.

### Allowed (read-only)

\`git status\`, \`git diff\`, \`git log\`, \`git show\`, \`git branch\` (list only), \`git rev-parse\`, \`git describe\`, \`git ls-files\`, \`git blame\`, \`git shortlog\`, \`git diff-tree\`, \`git cat-file\`

### Forbidden (never run — stop and report if tempted)

- **Discard / undo work:** \`git reset\`, \`git restore\`, \`git checkout\` / \`git switch\` when it would move HEAD or drop local changes, \`git clean\`, \`git stash\` / \`git stash pop\` / \`git stash drop\`
- **History / refs:** \`git revert\`, \`git rebase\`, \`git cherry-pick\`, \`git merge\`, \`git pull\`, \`git push\`, \`git commit\`, \`git add\`, \`git am\`
- **Destructive:** removing or rewriting \`.git\`, force-push, or aliases/scripts that perform the above

Inspect changes with \`git status\` / \`git diff\` / \`git log\` only. To fix files, use editor tools — **not** git reset/restore/checkout.`;

/** Short reminder for subagent system prompts. */
export const GIT_POLICY_SUBAGENT = `Git: read-only only (status, diff, log, show). Never reset, restore, checkout/switch to discard work, clean, stash, commit, or other mutating git commands.`;

/** Suggested bullet for spec ## Constraints when bootstrapping. */
export const GIT_POLICY_SPEC_CONSTRAINT =
  "Agents must not run mutating git commands (no reset, restore, checkout to discard changes, clean, stash, commit, etc.); read-only git (status, diff, log) only.";
