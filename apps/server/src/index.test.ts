import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { createStore } from "./store.js";

describe("session store", () => {
  it("creates a consent-gated session", async () => {
    const session = await (await createStore()).createSession("Bengali");
    assert.equal(session.state, "consent");
    assert.equal(session.language, "Bengali");
  });
});
