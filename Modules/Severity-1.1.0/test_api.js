import assert from "assert";
import { execFile } from "child_process";
import fs from "fs";
import os from "os";
import path from "path";

// Simple self-contained API test runner using Node.js native fetch and assert
async function runTests() {
  console.log("Starting Severity API integration test...");

  // Start the server programmatically as a background process
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "severity-v1-"));
  const serverProcess = execFile("node", ["server.js"], {
    env: {
      ...process.env,
      PORT: 4567,
      SEVERITY_DATA_FILE: path.join(dataDir, "legacy.json"),
      SEVERITY_V2_DATA_FILE: path.join(dataDir, "v2.json")
    }
  });
  
  // Wait 1.5 seconds for server to boot up
  await new Promise(resolve => setTimeout(resolve, 1500));

  const baseUrl = "http://localhost:4567";
  const testPatientCode = "TEST-PATIENT-99";

  try {
    // 1. Test GET route for non-existent patient (should return default pending structure)
    console.log("Testing GET route (new patient)...");
    const getRes1 = await fetch(`${baseUrl}/api/severity/${testPatientCode}`);
    assert.strictEqual(getRes1.status, 200, "GET initial state should return 200");
    
    const getJson1 = await getRes1.json();
    assert.strictEqual(getJson1.patient_code, testPatientCode);
    assert.strictEqual(getJson1.status, "pending");
    assert.deepStrictEqual(getJson1.scores, { total: 0, positive: 0, negative: 0, general: 0 });

    // 2. Test PUT route for saving passed assessment
    console.log("Testing PUT route (passed assessment)...");
    const putRes1 = await fetch(`${baseUrl}/api/severity/${testPatientCode}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "passed" })
    });
    assert.strictEqual(putRes1.status, 200, "PUT passed assessment should return 200");
    const putJson1 = await putRes1.json();
    assert.strictEqual(putJson1.success, true);
    assert.strictEqual(putJson1.data.status, "passed");

    // 3. Test GET route again to verify passed assessment is saved
    console.log("Testing GET route (verify passed)...");
    const getRes2 = await fetch(`${baseUrl}/api/severity/${testPatientCode}`);
    const getJson2 = await getRes2.json();
    assert.strictEqual(getJson2.status, "passed");

    // 4. Test PUT route for saving completed assessment
    console.log("Testing PUT route (completed assessment)...");
    const testItems = { "P1": 4, "N1": 2, "G1": 1 };
    const testScores = { total: 37, positive: 4, negative: 2, general: 1 };
    
    const putRes2 = await fetch(`${baseUrl}/api/severity/${testPatientCode}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "completed",
        scores: testScores,
        items: testItems
      })
    });
    assert.strictEqual(putRes2.status, 200, "PUT completed assessment should return 200");
    const putJson2 = await putRes2.json();
    assert.strictEqual(putJson2.success, true);
    assert.strictEqual(putJson2.data.status, "completed");
    assert.deepStrictEqual(putJson2.data.scores, testScores);
    assert.deepStrictEqual(putJson2.data.items, testItems);

    // 5. Test GET route again to verify completed assessment is persisted correctly
    console.log("Testing GET route (verify completed)...");
    const getRes3 = await fetch(`${baseUrl}/api/severity/${testPatientCode}`);
    const getJson3 = await getRes3.json();
    assert.strictEqual(getJson3.status, "completed");
    assert.deepStrictEqual(getJson3.scores, testScores);
    assert.deepStrictEqual(getJson3.items, testItems);

    console.log("\n====================================================");
    console.log(" SUCCESS: All integration tests passed successfully!");
    console.log("====================================================\n");
    
    // Cleanup
    serverProcess.kill();
    fs.rmSync(dataDir, { recursive: true, force: true });
    process.exit(0);

  } catch (error) {
    console.error("Test execution failed:", error);
    serverProcess.kill();
    fs.rmSync(dataDir, { recursive: true, force: true });
    process.exit(1);
  }
}

runTests();
