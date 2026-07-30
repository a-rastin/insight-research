import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { browserStorageAdapter, memoryStorageAdapter } = require("../src/storage-adapter.js");
test("browser adapter reports quota failures", () => {
  const error = Object.assign(new Error("full"), { name: "QuotaExceededError" });
  const adapter = browserStorageAdapter({ getItem: () => null, setItem: () => { throw error; } });
  assert.equal(adapter.write("kb", {}).reason, "quota_exceeded");
});
test("browser adapter reports disabled storage", () => {
  const adapter = browserStorageAdapter({ getItem: () => { throw new Error("denied"); }, setItem() {} });
  assert.equal(adapter.read("kb").reason, "storage_unavailable");
});
test("adapters report corrupt JSON", () => {
  const adapter = memoryStorageAdapter(); adapter.setRaw("kb", "{");
  assert.equal(adapter.read("kb").reason, "corrupt_json");
});
test("failed writes leave durable state unchanged for rollback", () => {
  const durable = JSON.stringify({ status: "pending" });
  const adapter = browserStorageAdapter({ getItem: () => durable, setItem: () => { throw new Error("disabled"); } });
  const working = { status: "approved" };
  assert.equal(adapter.write("kb", working).ok, false);
  Object.assign(working, { status: "pending" });
  assert.deepEqual(adapter.read("kb").value, working);
});
