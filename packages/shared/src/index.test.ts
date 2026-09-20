import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { nextInterviewState } from "./index";

describe("interview state machine", () => {
  it("moves through the deterministic states", () => {
    assert.equal(nextInterviewState("idle"), "language");
    assert.equal(nextInterviewState("interview"), "results");
    assert.equal(nextInterviewState("done"), "done");
  });
});
