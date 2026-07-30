import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { parseReport as parseCliReport } from "../scripts/ingest.mjs";

const require = createRequire(import.meta.url);
const engine = require("../src/ddi-engine.js");
const fixtureDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "reports");

function normalize(parsed) {
  return {
    drug: parsed.drug?.name || null,
    aliases: [...(parsed.drug?.aliases || [])].sort(),
    doses: [...(parsed.drug?.doseSuggestions || [])].sort(),
    interactions: parsed.interactions.map((item) => ({
      drugAName: item.drugAName,
      drugBName: item.drugBName,
      severity: item.severity,
      mechanism: item.mechanism,
      clinicalEffect: item.clinicalEffect,
      recommendation: item.recommendation,
      monitoring: item.monitoring,
      evidenceExcerpt: item.evidenceExcerpt,
      sequence: item.sequence
    }))
  };
}

for (const filename of fs.readdirSync(fixtureDir).sort()) {
  test(`browser and CLI adapters have parser parity for ${filename}`, () => {
    const filePath = path.join(fixtureDir, filename);
    const raw = fs.readFileSync(filePath, "utf8");
    const browser = engine.parseReportText(raw, filename, { version: "parity-test" });
    const cli = parseCliReport(raw, filename, { drugs: new Map(), version: "parity-test" });
    assert.deepEqual(normalize(browser), normalize(cli));
  });
}
