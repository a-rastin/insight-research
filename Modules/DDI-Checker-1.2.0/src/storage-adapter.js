(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.DDIStorage = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  function failure(error, operation, key) {
    const quota = error?.name === "QuotaExceededError" || error?.code === 22 || error?.code === 1014;
    return { ok: false, operation, key, reason: quota ? "quota_exceeded" : "storage_unavailable", error };
  }
  function browserStorageAdapter(storage) {
    return {
      read(key, fallback = null) {
        let raw;
        try { raw = storage.getItem(key); } catch (error) { return failure(error, "read", key); }
        if (raw == null) return { ok: true, value: fallback };
        try { return { ok: true, value: JSON.parse(raw) ?? fallback }; }
        catch (error) { return { ok: false, operation: "read", key, reason: "corrupt_json", error }; }
      },
      write(key, value) {
        try { storage.setItem(key, JSON.stringify(value)); return { ok: true }; }
        catch (error) { return failure(error, "write", key); }
      }
    };
  }
  function memoryStorageAdapter(initial = {}) {
    const values = new Map(Object.entries(initial).map(([key, value]) => [key, JSON.stringify(value)]));
    return {
      read(key, fallback = null) {
        if (!values.has(key)) return { ok: true, value: fallback };
        try { return { ok: true, value: JSON.parse(values.get(key)) ?? fallback }; }
        catch (error) { return { ok: false, operation: "read", key, reason: "corrupt_json", error }; }
      },
      write(key, value) { values.set(key, JSON.stringify(value)); return { ok: true }; },
      setRaw(key, raw) { values.set(key, raw); }
    };
  }
  return { browserStorageAdapter, memoryStorageAdapter };
});
