import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const contracts = new URL("../contracts/", import.meta.url);

async function load(name) {
  return JSON.parse(await readFile(new URL(name, contracts), "utf8"));
}

test("finding actions separate caller input from persisted audit fields", async () => {
  const schema = await load("ddi-v1.schema.json");
  const openapi = await load("openapi-v1.json");
  const request = schema.$defs.findingActionRequest;
  const response = schema.$defs.findingActionResponse;
  const serverOwned = ["actionId", "alertId", "actorId", "actorRole", "recordedAt"];

  assert.deepEqual(Object.keys(request.properties).sort(), ["action", "rationale"]);
  assert.equal(request.additionalProperties, false);
  for (const field of serverOwned) assert.ok(response.required.includes(field));
  const operation = openapi.paths["/checks/{checkId}/findings/{alertId}/actions"].post;
  assert.equal(operation.requestBody.content["application/json"].schema.$ref, "ddi-v1.schema.json#/$defs/findingActionRequest");
  assert.equal(operation.responses["201"].content["application/json"].schema.$ref, "ddi-v1.schema.json#/$defs/findingActionResponse");
});

test("lifecycle mutations publish request, response, and strong preconditions", async () => {
  const openapi = await load("openapi-v1.json");
  for (const action of ["review", "activate", "rollback"]) {
    const operation = openapi.paths[`/knowledge-revisions/{revisionId}/${action}`].post;
    assert.ok(operation.parameters.some((item) => item.$ref === "#/components/parameters/IfMatch"));
    assert.equal(operation.requestBody.$ref, "#/components/requestBodies/LifecycleTransition");
    assert.equal(operation.responses["200"].$ref, "#/components/responses/LifecycleTransition");
  }
  assert.equal(openapi.components.parameters.IfMatch.schema.pattern, '^"[^"]+"$');
});

test("coverage arrays have disjoint item schemas and fail-closed cardinality", async () => {
  const schema = await load("ddi-v1.schema.json");
  const response = schema.$defs.checkResponse;

  assert.equal(response.properties.resolvedMedications.items.$ref, "#/$defs/resolvedMedication");
  assert.equal(response.properties.unresolvedMedications.items.$ref, "#/$defs/unresolvedMedication");
  assert.equal(schema.$defs.resolvedMedication.properties.status.const, "resolved");
  assert.deepEqual(
    schema.$defs.unresolvedMedication.oneOf.map((item) => item.properties.status.const),
    ["ambiguous", "unknown"],
  );
  assert.equal(response.allOf[0].then.properties.unresolvedMedications.maxItems, 0);
  assert.equal(response.allOf[0].else.properties.unresolvedMedications.minItems, 1);
});
