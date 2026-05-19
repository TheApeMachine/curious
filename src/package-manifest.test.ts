import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  collectPackageManifestIssues,
  filesExcludeCompiledTests,
  normalizeBinEntries,
  packageManifestReady,
  type PackageManifest,
} from "./package-manifest.js";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

describe("normalizeBinEntries", () => {
  it("wraps a string bin as curious", () => {
    assert.deepEqual(normalizeBinEntries("./dist/index.js"), {
      curious: "./dist/index.js",
    });
  });

  it("returns a copy of object bin entries", () => {
    const bin = { curious: "./dist/index.js" };
    assert.deepEqual(normalizeBinEntries(bin), bin);
    assert.notEqual(normalizeBinEntries(bin), bin);
  });
});

describe("filesExcludeCompiledTests", () => {
  it("accepts dist test globs", () => {
    assert.equal(
      filesExcludeCompiledTests(["dist", "!dist/**/*.test.js"]),
      true,
    );
  });

  it("rejects files lists without test exclusions", () => {
    assert.equal(filesExcludeCompiledTests(["dist", "README.md"]), false);
  });
});

describe("collectPackageManifestIssues", () => {
  it("flags missing bin, files, and prepare", () => {
    const issues = collectPackageManifestIssues({
      name: "@theapemachine/curious",
      version: "0.1.0",
      type: "module",
      engines: { node: ">=18" },
    });
    assert.ok(issues.some((issue) => issue.path === "bin"));
    assert.ok(issues.some((issue) => issue.path === "files"));
    assert.ok(issues.some((issue) => issue.path === "scripts.prepare"));
  });

  it("passes a minimal publish-ready manifest", () => {
    const manifest: PackageManifest = {
      name: "@theapemachine/curious",
      version: "0.1.0",
      type: "module",
      bin: { curious: "./dist/index.js" },
      files: ["dist", "!dist/**/*.test.js", "!dist/**/*.test.d.ts", "README.md"],
      scripts: { prepare: "npm run build" },
      engines: { node: ">=18" },
    };
    assert.deepEqual(collectPackageManifestIssues(manifest), []);
    assert.equal(packageManifestReady(manifest), true);
  });
});

describe("package.json publish manifest", () => {
  it("repo package.json satisfies publish prerequisites", async () => {
    const raw = await readFile(path.join(repoRoot, "package.json"), "utf8");
    const manifest = JSON.parse(raw) as PackageManifest;
    const issues = collectPackageManifestIssues(manifest);
    assert.deepEqual(
      issues,
      [],
      issues.map((issue) => `${issue.path}: ${issue.message}`).join("; "),
    );
  });
});
