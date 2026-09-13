/**
 * Normalize NEXT_PUBLIC_API_BASE_URL for fetch paths that already start with `/api/v1`.
 *
 * Production Caddy proxies `/api/*` to FastAPI without stripping the prefix.
 * A base URL that ends in `/api` would otherwise become `/api/api/v1/...`.
 */
export function resolveApiBaseUrl(raw: string | undefined): string {
  const trimmed = (raw ?? '').trim().replace(/\/+$/, '');
  if (trimmed.toLowerCase().endsWith('/api')) {
    return trimmed.slice(0, -'/api'.length).replace(/\/+$/, '');
  }
  return trimmed;
}
