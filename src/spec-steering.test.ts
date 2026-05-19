import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  AGENT_STEERING_HEADING,
  agentSteeringForPhase,
  formatSteeringPromptBlock,
  stripAgentSteering,
} from "./spec-steering.js";

function specWithSteering(sectionBody: string): string {
  return [
    "## Vision",
    "",
    "Product goals.",
    "",
    AGENT_STEERING_HEADING,
    "",
    sectionBody,
    "",
    "## Roadmap",
    "",
    "- [ ] T1.1",
  ].join("\n");
}

describe("agentSteeringForPhase", () => {
  it("returns null for the overseer phase", () => {
    const body = specWithSteering("### Developer\n\n- Fix tests\n");
    assert.equal(agentSteeringForPhase(body, "overseer"), null);
  });

  it("returns null when ## Agent steering is missing", () => {
    const body = "## Vision\n\nGoals only.\n";
    assert.equal(agentSteeringForPhase(body, "develop"), null);
  });

  it("returns phase-specific Developer and Reviewer steering", () => {
    const body = specWithSteering(
      [
        "### Developer",
        "",
        "- Prefer small diffs",
        "",
        "### Reviewer",
        "",
        "- Check npm test output",
        "",
        "### Sync",
        "",
        "- Sync tail placeholder",
      ].join("\n"),
    );

    assert.equal(agentSteeringForPhase(body, "develop"), "- Prefer small diffs");
    assert.equal(agentSteeringForPhase(body, "review"), "- Check npm test output");
  });

  it("returns phase-specific Sync steering", () => {
    const body = specWithSteering(
      [
        "### Sync",
        "",
        "- Keep log rows factual",
        "",
        "### Developer",
        "",
        "- Not used for sync phase",
      ].join("\n"),
    );
    assert.equal(agentSteeringForPhase(body, "sync"), "- Keep log rows factual");
  });

  it("sanitizes forbidden steering lines for the active phase", () => {
    const body = specWithSteering(
      [
        "### Developer",
        "",
        "- Fix the bug",
        "- You must git commit before review",
        "",
        "### Reviewer",
        "",
        "- Review only",
      ].join("\n"),
    );

    const steering = agentSteeringForPhase(body, "develop");
    assert.match(steering ?? "", /Fix the bug/);
    assert.doesNotMatch(steering ?? "", /git commit/);
    assert.match(steering ?? "", /Curious omitted 1 steering line/);
  });

  it("returns null when phase steering is noop placeholder text", () => {
    const body = specWithSteering("### Developer\n\nnone\n");
    assert.equal(agentSteeringForPhase(body, "develop"), null);
  });

  it("returns shared steering when the section has no subsections", () => {
    const body = specWithSteering("- Read files before claiming PASS\n");
    assert.equal(
      agentSteeringForPhase(body, "develop"),
      "- Read files before claiming PASS",
    );
  });

  it("returns null when subsections exist but the phase block is missing", () => {
    const body = specWithSteering("### Reviewer\n\n- Review only\n");
    assert.equal(agentSteeringForPhase(body, "develop"), null);
  });
});

describe("stripAgentSteering", () => {
  it("removes the ## Agent steering section", () => {
    const body = specWithSteering("### Developer\n\n- Guidance\n");
    const stripped = stripAgentSteering(body);

    assert.doesNotMatch(stripped, /## Agent steering/);
    assert.match(stripped, /^## Vision/);
    assert.match(stripped, /## Roadmap/);
    assert.doesNotMatch(stripped, /Guidance/);
  });

  it("returns trimmed body when steering is absent", () => {
    const body = "## Vision\n\nGoals.\n";
    assert.equal(stripAgentSteering(body), body.trim());
  });
});

describe("formatSteeringPromptBlock", () => {
  it("formats develop steering with role-specific heading", () => {
    const block = formatSteeringPromptBlock("develop", "- Prefer small diffs");

    assert.match(block, /^## Agent steering \(overseer → Developer\)/);
    assert.match(block, /Corrective guidance from the overseer/);
    assert.match(block, /- Prefer small diffs$/);
  });

  it("uses the phase name when no role subsection exists", () => {
    const block = formatSteeringPromptBlock("overseer", "- Audit drift");
    assert.match(block, /^## Agent steering \(overseer → overseer\)/);
    assert.match(block, /- Audit drift$/);
  });
});
