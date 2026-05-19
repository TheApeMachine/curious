import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { analyzeRoadmap } from "./spec-roadmap.js";

describe("analyzeRoadmap", () => {
  it("returns empty status when ## Roadmap is missing", () => {
    assert.deepEqual(analyzeRoadmap("# Vision\n\nNo roadmap here.\n"), {
      totalTasks: 0,
      checkedTasks: 0,
      uncheckedTaskIds: [],
      complete: false,
    });
  });

  it("returns empty status when ## Roadmap has no task lines", () => {
    const body = "## Roadmap\n\n### Phase 1\n\n_No tasks yet._\n";
    assert.deepEqual(analyzeRoadmap(body), {
      totalTasks: 0,
      checkedTasks: 0,
      uncheckedTaskIds: [],
      complete: false,
    });
  });

  it("parses T* task IDs and collects unchecked IDs", () => {
    const body = [
      "## Roadmap",
      "",
      "- [ ] T1.1 — first task",
      "- [x] T1.2 — done",
      "- [ ] T2.3 — pending",
    ].join("\n");

    assert.deepEqual(analyzeRoadmap(body), {
      totalTasks: 3,
      checkedTasks: 1,
      uncheckedTaskIds: ["T1.1", "T2.3"],
      complete: false,
    });
  });

  it("parses M* milestone task IDs", () => {
    const body = "## Roadmap\n\n- [ ] M0 — bootstrap\n- [x] M1 — phase one\n";

    assert.deepEqual(analyzeRoadmap(body), {
      totalTasks: 2,
      checkedTasks: 1,
      uncheckedTaskIds: ["M0"],
      complete: false,
    });
  });

  it("treats [X] as checked (case insensitive)", () => {
    const body = "## Roadmap\n\n- [X] T1.1 — done\n";

    assert.deepEqual(analyzeRoadmap(body), {
      totalTasks: 1,
      checkedTasks: 1,
      uncheckedTaskIds: [],
      complete: true,
    });
  });

  it("detects completion when every task is checked", () => {
    const body = [
      "## Roadmap",
      "",
      "- [x] T1.1 — done",
      "- [x] T1.2 — done",
    ].join("\n");

    const status = analyzeRoadmap(body);
    assert.equal(status.complete, true);
    assert.deepEqual(status.uncheckedTaskIds, []);
    assert.equal(status.totalTasks, 2);
    assert.equal(status.checkedTasks, 2);
  });

  it("ignores non-roadmap checkbox lines without T/M task IDs", () => {
    const body = [
      "## Roadmap",
      "",
      "- [ ] T1.1 — real task",
      "- [x] R14 — requirement style (ignored)",
      "- [ ] Not a task line",
    ].join("\n");

    assert.deepEqual(analyzeRoadmap(body), {
      totalTasks: 1,
      checkedTasks: 0,
      uncheckedTaskIds: ["T1.1"],
      complete: false,
    });
  });

  it("only parses tasks inside ## Roadmap, not other sections", () => {
    const body = [
      "## Requirements",
      "",
      "- [ ] T9.9 — should not count",
      "",
      "## Roadmap",
      "",
      "- [x] T1.1 — counts",
    ].join("\n");

    assert.deepEqual(analyzeRoadmap(body), {
      totalTasks: 1,
      checkedTasks: 1,
      uncheckedTaskIds: [],
      complete: true,
    });
  });
});
