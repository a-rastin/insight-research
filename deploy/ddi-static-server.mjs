import { createReadStream, existsSync } from "node:fs";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";

const root = resolve(process.env.DDI_ROOT || "/opt/insight/Modules/DDI-Checker-1.2.0");
const registryRoot = resolve(process.env.DDI_REGISTRY_ROOT || resolve(root, "data"));
const port = Number(process.env.PORT || 8107);
const types = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".json": "application/json" };

function json(response, status, body) {
  const bytes = Buffer.from(JSON.stringify(body));
  response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store", "Content-Length": bytes.length });
  response.end(bytes);
}

const server = createServer((request, response) => {
  const pathname = new URL(request.url, "http://module.local").pathname;
  if (request.method !== "GET") return json(response, 405, { error: "method-not-allowed" });
  if (pathname === "/healthz") return json(response, 200, { status: "live", module: "ddi-checker" });
  if (pathname === "/readyz") return json(response, 503, {
    status: "not-ready",
    module: "ddi-checker",
    reason: "production-rest-seam-unavailable"
  });

  const relative = pathname === "/" ? "index.html" : decodeURIComponent(pathname.slice(1));
  const registryFile = /^data\/active-kb\.(js|json)$/.test(relative);
  const file = registryFile ? resolve(registryRoot, relative.slice(5)) : resolve(root, relative);
  const base = registryFile ? registryRoot : root;
  const allowed = file.startsWith(`${base}${sep}`) && /^(index\.html|src\/[\w.-]+\.(css|js)|data\/active-kb\.(js|json))$/.test(relative);
  if (!allowed || !existsSync(file)) return json(response, 404, { error: "not-found" });
  response.writeHead(200, { "Content-Type": types[extname(file)] || "application/octet-stream", "Cache-Control": "no-store" });
  createReadStream(file).pipe(response);
});

server.listen(port, "127.0.0.1");
const stop = () => server.close(() => process.exit(0));
process.on("SIGTERM", stop);
process.on("SIGINT", stop);
