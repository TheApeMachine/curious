import os from "node:os";
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  REVIEW_FAIL_WORKFLOW_NOTE,
  SOURCE_OF_TRUTH_SECTION,
  WORKFLOW_SPEC_CONSTRAINTS,
  buildWorkflowPolicySection,
  hostArchLabel,
  isArm64Host,
  sanitizeSteering,
} from "./workflow-policy.js";

describe("hostArchLabel", () => {
  it("returns the Node os.arch() value", () => {
    assert.equal(hostArchLabel(), os.arch());
  });
});

describe("isArm64Host", () => {
  it("is true when hostArchLabel is arm64", () => {
    assert.equal(isArm64Host(), hostArchLabel() === "arm64");
  });
});

describe("sanitizeSteering", () => {
  it("keeps steering lines with no forbidden content", () => {
    const input = "- Focus on unit tests\n- Read files before claiming PASS\n";
    assert.deepEqual(sanitizeSteering(input), {
      text: input.trim(),
      strippedCount: 0,
    });
  });

  it("strips git commit and staging directives", () => {
    const input = [
      "- Fix the parser bug",
      "- You must git commit before review",
      "- git add the test file",
    ].join("\n");

    const result = sanitizeSteering(input);

    assert.equal(result.strippedCount, 2);
    assert.match(result.text, /Fix the parser bug/);
    assert.doesNotMatch(result.text, /git commit|git add/);
    assert.match(result.text, /Curious omitted 2 steering line/);
  });

  it("strips worktree and CI artifact lines", () => {
    const input = [
      "* Use a git worktree for isolation",
      "* Paste GitHub Actions output",
      "* Require CI artifact proof",
      "- Keep host-only verification",
    ].join("\n");

    const result = sanitizeSteering(input);

    assert.equal(result.strippedCount, 3);
    assert.match(result.text, /^- Keep host-only verification/);
    assert.match(result.text, /Curious omitted 3 steering line/);
  });

  it("strips amd64-on-arm and branch-tip HEAD demands", () => {
    const input = [
      "- Paste amd64 bench output on arm64",
      "- branch-tip must match HEAD before PASS",
      "- Keep improving tests",
    ].join("\n");

    const result = sanitizeSteering(input);

    assert.equal(result.strippedCount, 2);
    assert.match(result.text, /^- Keep improving tests/);
    assert.match(result.text, /Curious omitted 2 steering line/);
  });

  it("returns empty text when every line is forbidden", () => {
    const input = "- must commit before continuing\n- use a worktree\n";
    assert.deepEqual(sanitizeSteering(input), {
      text: "",
      strippedCount: 2,
    });
  });
});

describe("buildWorkflowPolicySection", () => {
  it("builds an arm64 section with host-only verification guidance", () => {
    const section = buildWorkflowPolicySection("arm64");

    assert.match(section, /^## Workflow \(binding — human \+ host\)/);
    assert.match(section, /\*\*Curious host:\*\* `arm64`/);
    assert.match(section, /This run is on arm64/);
    assert.match(section, /\*\*not\*\* required to execute here/);
    assert.match(section, /### Commits \(human only\)/);
    assert.match(section, /### Verification \(this machine only\)/);
    assert.match(section, new RegExp(SOURCE_OF_TRUTH_SECTION.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  });

  it("builds an x64 section that still forbids CI and agent commits", () => {
    const section = buildWorkflowPolicySection("x64");

    assert.match(section, /\*\*Curious host:\*\* `x64`/);
    assert.match(section, /This run is on x64/);
    assert.match(section, /still do not require CI or agent commits/);
    assert.match(section, /When in doubt — read the files/);
  });

  it("builds a generic section for other architectures", () => {
    const section = buildWorkflowPolicySection("ppc64");

    assert.match(section, /\*\*Curious host:\*\* `ppc64`/);
    assert.match(section, /Host architecture.*`ppc64`/);
    assert.match(section, /do not require CI for verification/);
  });

  it("treats amd64 like x64 in the host note", () => {
    const section = buildWorkflowPolicySection("amd64");

    assert.match(section, /This run is on amd64/);
    assert.match(section, /Run amd64-tagged tests when present/);
  });
});

describe("workflow policy constants", () => {
  it("exports a review-fail workflow override note", () => {
    assert.match(REVIEW_FAIL_WORKFLOW_NOTE, /Workflow override/);
    assert.match(REVIEW_FAIL_WORKFLOW_NOTE, /git commit/);
    assert.match(REVIEW_FAIL_WORKFLOW_NOTE, /read the files/);
  });

  it("exports bootstrap workflow constraint bullets", () => {
    assert.match(WORKFLOW_SPEC_CONSTRAINTS, /Human commits only/);
    assert.match(WORKFLOW_SPEC_CONSTRAINTS, /local host architecture/);
    assert.match(WORKFLOW_SPEC_CONSTRAINTS, /file content is the source of truth/);
  });
});
