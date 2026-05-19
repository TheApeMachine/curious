# Publishing `@theapemachine/curious`

Manual checklist for verifying the npm package before a human publishes. Curious agents do **not** run `npm publish` — this documents prerequisites and local verification only.

## Prerequisites

Before publishing:

- [ ] **npm account** with access to the `@theapemachine` scope (scoped packages require `--access public` on first publish unless org settings allow otherwise).
- [ ] **`npm login`** (or CI token with publish rights) for the registry you target (`https://registry.npmjs.org` by default).
- [ ] **Clean build** — `npm test` passes on this host (build + unit tests).
- [ ] **`CURSOR_API_KEY`** — not required to publish; end users need it to run agent commands.

## Package layout (verified in T4.1)

| Field | Expected | Purpose |
|-------|----------|---------|
| `bin.curious` | `./dist/index.js` | CLI entry (must include `#!/usr/bin/env node` shebang in compiled output) |
| `files` | `dist`, `README.md`, `curious.config.example.json`, test exclusions | Tarball whitelist — **must not** ship `dist/**/*.test.js` |
| `scripts.prepare` | `npm run build` | Ensures `dist/` exists on `npm install` from git or registry |
| `type` | `"module"` | NodeNext ESM CLI |
| `engines.node` | `>=18` | Matches AGENTS.md runtime |

Automated guard: `src/package-manifest.test.ts` reads root `package.json` and asserts the above via `collectPackageManifestIssues`.

## Local verification

From the repository root:

```bash
npm test
npm run pack:check
```

`pack:check` runs `npm run build` then `npm pack --dry-run` so you can inspect tarball contents without writing a `.tgz`.

**Expect in the tarball:**

- `dist/index.js` and production modules (no `*.test.js` / `*.test.d.ts`)
- `README.md`
- `curious.config.example.json`

**Expect absent:**

- `src/`, `spec/`, test fixtures, `.curious/`, local config

Optional smoke after pack:

```bash
npm pack
tar -tzf theapemachine-curious-*.tgz | head -30
npm install -g theapemachine-curious-*.tgz
curious --help
```

## Publish (human only)

```bash
npm test
npm run pack:check
npm publish --access public
```

Use `--dry-run` on `npm publish` first if you want a registry-side rehearsal without releasing.

Version bumps and changelog conventions are **T4.2** — do not change semver in agent cycles unless that task is active.

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `403` on publish | No scope access / not logged in | `npm login`; confirm `@theapemachine` permissions |
| `curious: command not found` after global install | `prepare` did not run or `bin` path wrong | Re-run `npm run build`; verify `bin.curious` → `./dist/index.js` |
| Tarball includes `*.test.js` | Missing `!dist/**/*.test.js` in `files` | Fix `package.json` `files`; re-run `npm run pack:check` |
| `prepare` fails on install | TypeScript compile error | Fix `npm run build` before publishing |
