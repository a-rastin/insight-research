import { isUuid } from "./panss.js";

function majorIs2(value) {
  return typeof value === "string" && value.split(".", 1)[0] === "2";
}

function futureUtc(value) {
  return typeof value === "string" && value.endsWith("Z") && Number.isFinite(Date.parse(value)) && Date.parse(value) > Date.now();
}

export function validateSession(payload, schemaVersion) {
  const session = payload?.session;
  const user = payload?.user;
  const gates = payload?.gates;
  const compatibility = payload?.compatibility;
  if (!majorIs2(schemaVersion) || !majorIs2(payload?.interfaceVersion) || payload?.authenticated !== true ||
      payload?.authorized !== true || !isUuid(session?.id) || session?.active !== true || !futureUtc(session?.expiresAt) ||
      !isUuid(user?.id) || typeof user?.username !== "string" || !user.username ||
      !["admin", "psychiatrist"].includes(user?.role) || gates?.passwordChangeRequired !== false ||
      gates?.disclaimerRequired !== false || typeof gates?.disclaimerVersion !== "string" || !gates.disclaimerVersion ||
      !Number.isInteger(compatibility?.legacyUserId) || compatibility.legacyUserId < 1 ||
      !["user", null].includes(compatibility?.legacyRole)) {
    return null;
  }
  return { actorId: user.id, sessionId: session.id, role: user.role };
}

export async function fetchSession(authBaseUrl, cookie, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${authBaseUrl.replace(/\/$/, "")}/api/auth/v2/session`, {
      headers: cookie ? { Cookie: cookie } : {},
      signal: controller.signal
    });
    if (response.status === 401 || response.status === 403) return { denied: true };
    if (!response.ok) return { unavailable: true };
    let payload;
    try {
      payload = await response.json();
    } catch {
      return { unavailable: true };
    }
    const session = validateSession(payload, response.headers.get("x-schema-version"));
    return session ? { session } : { denied: true };
  } catch {
    return { unavailable: true };
  } finally {
    clearTimeout(timeout);
  }
}

export async function authenticationReachable(authBaseUrl, timeoutMs) {
  const result = await fetchSession(authBaseUrl, "", timeoutMs);
  return result.denied === true || Boolean(result.session);
}
