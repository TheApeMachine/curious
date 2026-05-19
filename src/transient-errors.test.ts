import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { Code, ConnectError } from "@connectrpc/connect";
import { AgentBusyError, CursorAgentError } from "@cursor/sdk";
import {
  errorMessage,
  isAgentBusyError,
  isTransientError,
} from "./transient-errors.js";

function errnoError(code: string, message = code): NodeJS.ErrnoException {
  const err = new Error(message) as NodeJS.ErrnoException;
  err.code = code;
  return err;
}

describe("errorMessage", () => {
  it("returns message from Error instances", () => {
    assert.equal(errorMessage(new Error("boom")), "boom");
  });

  it("stringifies non-Error values", () => {
    assert.equal(errorMessage("plain"), "plain");
    assert.equal(errorMessage(42), "42");
  });
});

describe("isTransientError", () => {
  it("uses isRetryable for CursorAgentError", () => {
    assert.equal(
      isTransientError(new CursorAgentError("retry", { isRetryable: true })),
      true,
    );
    assert.equal(
      isTransientError(new CursorAgentError("nope", { isRetryable: false })),
      false,
    );
  });

  it("detects transient ConnectError codes", () => {
    for (const code of [
      Code.Unavailable,
      Code.DeadlineExceeded,
      Code.ResourceExhausted,
      Code.Aborted,
      Code.Internal,
    ]) {
      assert.equal(isTransientError(new ConnectError("svc down", code)), true);
    }
  });

  it("returns false for non-transient ConnectError codes", () => {
    assert.equal(isTransientError(new ConnectError("missing", Code.NotFound)), false);
    assert.equal(
      isTransientError(new ConnectError("bad req", Code.InvalidArgument)),
      false,
    );
  });

  it("detects transient Node errno codes", () => {
    for (const code of [
      "ECONNRESET",
      "ETIMEDOUT",
      "ECONNREFUSED",
      "EPIPE",
      "ENOTFOUND",
      "EAI_AGAIN",
    ]) {
      assert.equal(isTransientError(errnoError(code)), true);
    }
  });

  it("returns false for non-transient errno codes", () => {
    assert.equal(isTransientError(errnoError("EACCES")), false);
  });

  it("recurses through error cause chain", () => {
    const outer = new Error("outer", { cause: errnoError("ECONNREFUSED") });
    assert.equal(isTransientError(outer), true);
  });

  it("matches transient substrings in error messages", () => {
    assert.equal(isTransientError(new Error("read ECONNRESET")), true);
    assert.equal(isTransientError(new Error("connect ETIMEDOUT")), true);
    assert.equal(isTransientError(new Error("socket hang up")), true);
    assert.equal(isTransientError(new Error("network error during fetch")), true);
  });

  it("returns false for unrelated errors", () => {
    assert.equal(isTransientError(new Error("syntax error")), false);
    assert.equal(isTransientError("not an error object"), false);
  });
});

describe("isAgentBusyError", () => {
  it("returns true for AgentBusyError instances", () => {
    assert.equal(isAgentBusyError(new AgentBusyError("busy")), true);
  });

  it("matches already has active run in message", () => {
    assert.equal(
      isAgentBusyError(new Error("Agent already has active run xyz")),
      true,
    );
  });

  it("returns false for unrelated errors", () => {
    assert.equal(isAgentBusyError(new Error("connection refused")), false);
    assert.equal(isAgentBusyError(new CursorAgentError("other")), false);
  });
});
