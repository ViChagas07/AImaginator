const SENSITIVE_KEYS = new Set([
  "prompt",
  "email",
  "e-mail",
  "ip",
  "ip_address",
  "user_id",
  "generation_id",
  "token",
  "access_token",
  "refresh_token",
  "authorization",
  "cookie",
  "url",
  "signed_url",
  "object_key",
]);

const SENSITIVE_FRAGMENTS = [
  "prompt",
  "token",
  "secret",
  "password",
  "email",
  "object_key",
  "signed_url",
  "url",
];

function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase();
  return (
    SENSITIVE_KEYS.has(lowered) ||
    SENSITIVE_FRAGMENTS.some((fragment) => lowered.includes(fragment))
  );
}

const EMAIL = /[\w.+-]+@[\w-]+\.[\w.-]+/g;
const IPV4 = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;
const SIGNED_URL = /(X-Amz-Signature=|sig=)[^&\s]+/gi;
const BEARER = /Bearer\s+[A-Za-z0-9._~+/-]+=*/gi;
const JWT = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g;
const KEY_VALUE = /\b(prompt|seed|email|e-mail|ip|token|object_key|url)\s*[:=]\s*[^\s,&;]+/gi;

export function scrubText(value: string): string {
  return value
    .replace(EMAIL, "[Filtered]")
    .replace(IPV4, "[Filtered]")
    .replace(SIGNED_URL, "$1[Filtered]")
    .replace(BEARER, "Bearer [Filtered]")
    .replace(JWT, "[Filtered]")
    .replace(KEY_VALUE, "$1=[Filtered]");
}

function scrubValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(scrubValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        isSensitiveKey(key) ? "[Filtered]" : scrubValue(item),
      ]),
    );
  }
  return typeof value === "string" ? scrubText(value) : value;
}

export function scrubSentryEvent<T>(event: T): T {
  const record = event as Record<string, unknown>;
  delete record.user;
  if (typeof record.message === "string") {
    record.message = scrubText(record.message);
  }
  const request = record.request as Record<string, unknown> | undefined;
  if (request) {
    delete request.data;
    delete request.cookies;
    delete request.query_string;
    if (request.headers) request.headers = scrubValue(request.headers);
    if (typeof request.url === "string") request.url = scrubText(request.url);
  }
  const exception = record.exception as
    | {values?: Array<Record<string, unknown>>}
    | undefined;
  for (const value of exception?.values ?? []) {
    if (typeof value.value === "string") value.value = scrubText(value.value);
  }
  const breadcrumbs = record.breadcrumbs as
    | {values?: Array<Record<string, unknown>>}
    | undefined;
  for (const breadcrumb of breadcrumbs?.values ?? []) {
    if (typeof breadcrumb.message === "string") {
      breadcrumb.message = scrubText(breadcrumb.message);
    }
    if (breadcrumb.data) breadcrumb.data = scrubValue(breadcrumb.data);
  }
  record.extra = scrubValue(record.extra ?? {});
  record.contexts = scrubValue(record.contexts ?? {});
  record.tags = scrubValue(record.tags ?? {});
  return event;
}

export function scrubSentryBreadcrumb<T>(breadcrumb: T): T {
  const record = breadcrumb as Record<string, unknown>;
  if (typeof record.message === "string") {
    record.message = scrubText(record.message);
  }
  if (record.data) record.data = scrubValue(record.data);
  return breadcrumb;
}
