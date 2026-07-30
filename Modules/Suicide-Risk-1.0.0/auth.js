function isUuid(value) {
  return typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value);
}

function validateSession(payload, schemaVersion) {
  const session = payload?.session;
  const user = payload?.user;
  const gates = payload?.gates;
  if (schemaVersion?.split(".", 1)[0] !== "2" || payload?.interfaceVersion?.split(".", 1)[0] !== "2" ||
      payload?.authenticated !== true || payload?.authorized !== true || !isUuid(session?.id) || session?.active !== true ||
      typeof session?.expiresAt !== "string" || !session.expiresAt.endsWith("Z") || Date.parse(session.expiresAt) <= Date.now() ||
      !isUuid(user?.id) || !["admin", "psychiatrist"].includes(user?.role) || gates?.passwordChangeRequired !== false ||
      gates?.disclaimerRequired !== false) return null;
  return { actorId: user.id, sessionId: session.id, role: user.role };
}

async function fetchSession(baseUrl, cookie, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/auth/v2/session`, {
      headers: cookie ? { Cookie: cookie } : {},
      signal: controller.signal
    });
    if (response.status === 401 || response.status === 403) return { denied: true };
    if (!response.ok) return { unavailable: true };
    const payload = await response.json().catch(() => null);
    const session = validateSession(payload, response.headers.get("x-schema-version"));
    return session ? { session } : { denied: true };
  } catch {
    return { unavailable: true };
  } finally {
    clearTimeout(timeout);
  }
}

async function authenticationReachable(baseUrl, timeoutMs) {
  const result = await fetchSession(baseUrl, "", timeoutMs);
  return result.denied === true || Boolean(result.session);
}

module.exports = { authenticationReachable, fetchSession, validateSession };
