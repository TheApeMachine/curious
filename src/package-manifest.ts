export interface PackageManifest {
  name?: string;
  version?: string;
  bin?: string | Record<string, string>;
  files?: string[];
  scripts?: Record<string, string>;
  engines?: { node?: string };
  type?: string;
}

export interface PackageManifestIssue {
  path: string;
  message: string;
}

export const EXPECTED_BIN_ENTRY = "./dist/index.js";

export function normalizeBinEntries(
  bin: PackageManifest["bin"],
): Record<string, string> {
  if (!bin) {
    return {};
  }
  if (typeof bin === "string") {
    return { curious: bin };
  }
  return { ...bin };
}

export function filesExcludeCompiledTests(files: string[]): boolean {
  return files.some(
    (entry) =>
      entry === "!dist/**/*.test.js" ||
      entry === "!dist/**/*.test.d.ts" ||
      entry === "!**/*.test.js",
  );
}

export function collectPackageManifestIssues(
  manifest: PackageManifest,
): PackageManifestIssue[] {
  const issues: PackageManifestIssue[] = [];

  if (!manifest.name) {
    issues.push({ path: "name", message: "package name is required" });
  }
  if (!manifest.version) {
    issues.push({ path: "version", message: "package version is required" });
  }

  const binEntries = normalizeBinEntries(manifest.bin);
  if (Object.keys(binEntries).length === 0) {
    issues.push({ path: "bin", message: "bin entry is required for the CLI" });
  } else {
    if (!binEntries.curious) {
      issues.push({
        path: "bin.curious",
        message: 'bin must expose the "curious" command',
      });
    } else if (binEntries.curious !== EXPECTED_BIN_ENTRY) {
      issues.push({
        path: "bin.curious",
        message: `bin.curious must point to ${EXPECTED_BIN_ENTRY}`,
      });
    }
  }

  const files = manifest.files ?? [];
  if (files.length === 0) {
    issues.push({
      path: "files",
      message: "files whitelist is required so tests are not published",
    });
  } else {
    if (!files.includes("dist")) {
      issues.push({ path: "files", message: 'files must include "dist"' });
    }
    if (!files.includes("README.md")) {
      issues.push({ path: "files", message: 'files must include "README.md"' });
    }
    if (!filesExcludeCompiledTests(files)) {
      issues.push({
        path: "files",
        message:
          "files must exclude compiled test output (e.g. !dist/**/*.test.js)",
      });
    }
  }

  const prepare = manifest.scripts?.prepare ?? "";
  if (!prepare.includes("build")) {
    issues.push({
      path: "scripts.prepare",
      message: 'scripts.prepare must run build (e.g. "npm run build")',
    });
  }

  if (manifest.type !== "module") {
    issues.push({ path: "type", message: 'type must be "module" for ESM CLI' });
  }

  if (!manifest.engines?.node) {
    issues.push({ path: "engines.node", message: "engines.node is required" });
  }

  return issues;
}

export function packageManifestReady(manifest: PackageManifest): boolean {
  return collectPackageManifestIssues(manifest).length === 0;
}
