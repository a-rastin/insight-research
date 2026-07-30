import { createHmac, randomBytes, timingSafeEqual } from "crypto";

function signature(secret, value) {
  return createHmac("sha256", secret).update(value).digest("base64url");
}

export function mintCsrf(secret, sessionId) {
  const nonce = randomBytes(24).toString("base64url");
  return `${nonce}.${signature(secret, `${sessionId}.${nonce}`)}`;
}

export function verifyCsrf(secret, sessionId, cookieToken, headerToken) {
  if (typeof cookieToken !== "string" || typeof headerToken !== "string") return false;
  const cookie = Buffer.from(cookieToken);
  const header = Buffer.from(headerToken);
  if (cookie.length !== header.length || !timingSafeEqual(cookie, header)) return false;
  const separator = cookieToken.lastIndexOf(".");
  if (separator < 1) return false;
  const nonce = cookieToken.slice(0, separator);
  const supplied = Buffer.from(cookieToken.slice(separator + 1));
  const expected = Buffer.from(signature(secret, `${sessionId}.${nonce}`));
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}
