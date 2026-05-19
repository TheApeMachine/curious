import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("npm test wiring", () => {
  it("runs node:test on compiled dist output", () => {
    assert.equal(typeof describe, "function");
  });
});
