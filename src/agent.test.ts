import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { buildAgentOptions } from "./agent.js";
import { CURIOUS_MODEL } from "./model.js";
import type { CuriousConfig } from "./types.js";

function baseConfig(overrides: Partial<CuriousConfig> = {}): CuriousConfig {
  return {
    specPath: "/project/spec/SPEC.md",
    cwd: "/project",
    runtime: "local",
    model: CURIOUS_MODEL,
    cycleDelayMs: 0,
    maxCycles: 0,
    overseerEveryNCycles: 5,
    overseerOnReviewFailStreak: 2,
    ...overrides,
  };
}

describe("buildAgentOptions", () => {
  const priorApiKey = process.env.CURSOR_API_KEY;

  beforeEach(() => {
    process.env.CURSOR_API_KEY = "cursor_test_key";
  });

  afterEach(() => {
    if (priorApiKey === undefined) {
      delete process.env.CURSOR_API_KEY;
    } else {
      process.env.CURSOR_API_KEY = priorApiKey;
    }
  });

  it("throws when CURSOR_API_KEY is missing", () => {
    delete process.env.CURSOR_API_KEY;
    assert.throws(
      () => buildAgentOptions(baseConfig()),
      /Missing CURSOR_API_KEY/,
    );
  });

  it("wires local runtime with cwd and settingSources", () => {
    const options = buildAgentOptions(
      baseConfig({ settingSources: ["project", "user"] }),
    );
    assert.deepEqual(options.local, {
      cwd: "/project",
      settingSources: ["project", "user"],
    });
    assert.equal(options.cloud, undefined);
  });

  it("throws when cloud runtime has no cloud.repos", () => {
    assert.throws(
      () => buildAgentOptions(baseConfig({ runtime: "cloud" })),
      /cloud\.repos/,
    );
  });

  it("wires cloud runtime with repos and PR defaults", () => {
    const options = buildAgentOptions(
      baseConfig({
        runtime: "cloud",
        cloud: {
          repos: [{ url: "https://github.com/org/repo", startingRef: "main" }],
        },
      }),
    );
    assert.equal(options.local, undefined);
    assert.deepEqual(options.cloud?.repos, [
      { url: "https://github.com/org/repo", startingRef: "main" },
    ]);
    assert.equal(options.cloud?.autoCreatePR, false);
    assert.equal(options.cloud?.skipReviewerRequest, true);
    assert.equal(options.cloud?.workOnCurrentBranch, false);
  });

  it("passes explicit cloud PR flags through to SDK options", () => {
    const options = buildAgentOptions(
      baseConfig({
        runtime: "cloud",
        cloud: {
          repos: [{ url: "https://github.com/org/repo" }],
          autoCreatePR: true,
          skipReviewerRequest: false,
          workOnCurrentBranch: true,
        },
      }),
    );
    assert.equal(options.cloud?.autoCreatePR, true);
    assert.equal(options.cloud?.skipReviewerRequest, false);
    assert.equal(options.cloud?.workOnCurrentBranch, true);
  });
});
