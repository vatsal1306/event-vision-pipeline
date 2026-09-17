/**
 * Helpers for gallery preview URLs returned by the API.
 *
 * Previews are HMAC-signed FastAPI routes served under `/api/...`. Caddy
 * proxies that prefix to the backend. The backend `API_BASE_URL` is often
 * `http://localhost:8000` or an internal Docker hostname, which the browser
 * cannot load. Always rebuild the URL from the path + the public API base.
 */

import { resolveApiBaseUrl } from '@/lib/resolve-api-base-url';

function originFromEnv(raw: string | undefined): string | null {
  if (!raw?.trim()) {
    return null;
  }
  try {
    return new URL(raw.trim()).origin;
  } catch {
    return null;
  }
}

/**
 * Return the `/api/...` path and query from an absolute or relative media URL.
 */
export function extractApiMediaPath(src: string): string | null {
  if (!src) {
    return null;
  }
  if (src.startsWith('/api/')) {
    return src;
  }
  try {
    const url = new URL(src);
    if (url.pathname.startsWith('/api/')) {
      return `${url.pathname}${url.search}`;
    }
  } catch {
    return null;
  }
  return null;
}

function shouldUseSameOriginPath(apiBase: string): boolean {
  if (!apiBase) {
    return true;
  }
  const apiOrigin = originFromEnv(apiBase);
  const appOrigin = originFromEnv(process.env.NEXT_PUBLIC_APP_URL);
  return Boolean(apiOrigin && appOrigin && apiOrigin === appOrigin);
}

/**
 * Turn an API proxy URL into a browser-loadable src.
 *
 * Same-origin deployments (Caddy) get a relative `/api/...` path. Local
 * split-port development prefixes `NEXT_PUBLIC_API_BASE_URL`.
 */
export function toBrowserMediaSrc(src: string): string {
  if (!src || src.startsWith('blob:') || src.startsWith('data:')) {
    return src;
  }

  const apiPath = extractApiMediaPath(src);
  if (!apiPath) {
    return src;
  }

  const apiBase = resolveApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);
  if (shouldUseSameOriginPath(apiBase)) {
    return apiPath;
  }
  return `${apiBase}${apiPath}`;
}

/**
 * Normalize a nullable API proxy URL for use in `<img>`.
 */
export function resolveProxyUrl(src: string | null | undefined): string | null {
  if (src == null || src === '') {
    return src ?? null;
  }
  return toBrowserMediaSrc(src);
}

/** Intrinsic widths, in pixels, of the renditions the backend generates. */
const RENDITION_WIDTHS = {
  thumb: 480,
  preview: 1280,
  full: 2048,
} as const;

interface PhotoRenditions {
  thumbUrl: string | null;
  previewUrl: string | null;
  proxyUrl: string | null;
}

/**
 * Build an `<img srcset>` value from a photo's available renditions.
 *
 * Widths are the backend's configured maximums rather than the true pixel
 * width of each object, which is close enough for the browser to pick
 * sensibly and avoids a per-photo metadata round trip. Photos that predate the
 * rendition ladder collapse to a single candidate.
 */
export function buildPhotoSrcSet(photo: PhotoRenditions): string | undefined {
  const candidates = [
    [photo.thumbUrl, RENDITION_WIDTHS.thumb],
    [photo.previewUrl, RENDITION_WIDTHS.preview],
    [photo.proxyUrl, RENDITION_WIDTHS.full],
  ] as const;

  const seen = new Set<string>();
  const entries: string[] = [];
  for (const [url, width] of candidates) {
    if (!url || seen.has(url)) {
      continue;
    }
    seen.add(url);
    entries.push(`${url} ${width}w`);
  }

  return entries.length > 1 ? entries.join(', ') : undefined;
}
