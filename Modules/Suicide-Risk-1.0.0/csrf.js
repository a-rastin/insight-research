const { createHmac, randomBytes, timingSafeEqual } = require("node:crypto");

function sign(secret, value) {
  return createHmac("sha256", secret).update(value).digest("base64url");
}

function mintCsrf(secret, sessionId) {
  const nonce = randomBytes(24).toString("base64url");
  return `${nonce}.${sign(secret, `${sessionId}.${nonce}`)}`;
}

function verifyCsrf(secret, sessionId, cookieToken, headerToken) {
  if (typeof cookieToken !== "string" || typeof headerToken !== "string") return false;
  const cookie = Buffer.from(cookieToken);
  const header = Buffer.from(headerToken);
  if (cookie.length !== header.length || !timingSafeEqual(cookie, header)) return false;
  const separator = cookieToken.lastIndexOf(".");
  if (separator < 1) return false;
  const supplied = Buffer.from(cookieToken.slice(separator + 1));
  const expected = Buffer.from(sign(secret, `${sessionId}.${cookieToken.slice(0, separator)}`));
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}

module.exports = { mintCsrf, verifyCsrf };
