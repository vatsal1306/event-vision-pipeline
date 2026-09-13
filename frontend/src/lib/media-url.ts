/**
 * Helpers for gallery preview URLs returned by the API.
 *
 * Previews are HMAC-signed FastAPI routes, not a public CDN. next/image
 * optimization requires every hostname in `images.remotePatterns` and also
 * fetches the URL from inside the frontend container — both fail in
 * production where the API is served on the same public host via Caddy.
 */

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

function configuredMediaOrigins(): Set<string> {
  const origins = new Set<string>();
  for (const raw of [process.env.NEXT_PUBLIC_APP_URL, process.env.NEXT_PUBLIC_API_BASE_URL]) {
    const origin = originFromEnv(raw);
    if (origin) {
      origins.add(origin);
    }
  }
  return origins;
}

function isApiPreviewPath(pathname: string): boolean {
  return pathname.includes('/api/') && pathname.includes('/preview');
}

/**
 * Return true when next/image must skip the optimizer and render a plain img.
 */
export function shouldBypassImageOptimization(src: string): boolean {
  if (!src) {
    return false;
  }
  if (src.startsWith('blob:') || src.startsWith('data:')) {
    return true;
  }
  if (src.startsWith('/')) {
    return isApiPreviewPath(src);
  }

  try {
    const url = new URL(src);
    const isLoopback = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
    const isSigned = url.searchParams.has('sig') && url.searchParams.has('expires');
    return isLoopback || isApiPreviewPath(url.pathname) || isSigned;
  } catch {
    return false;
  }
}

/**
 * Prefer a same-origin relative path so the browser hits Caddy `/api/*`.
 *
 * Absolute `https://spotme.../api/v1/.../preview` URLs are treated as remote
 * by next/image even when they match the page origin.
 */
export function toBrowserMediaSrc(src: string): string {
  if (!src || src.startsWith('/') || src.startsWith('blob:') || src.startsWith('data:')) {
    return src;
  }

  try {
    const url = new URL(src);
    if (!url.pathname.startsWith('/api/')) {
      return src;
    }

    const sameAsPage =
      typeof window !== 'undefined' && url.origin === window.location.origin;
    if (sameAsPage || configuredMediaOrigins().has(url.origin)) {
      return `${url.pathname}${url.search}`;
    }
    return src;
  } catch {
    return src;
  }
}

/**
 * Normalize a nullable API proxy URL for use in `<img>` / next/image.
 */
export function resolveProxyUrl(src: string | null | undefined): string | null {
  if (src == null || src === '') {
    return src ?? null;
  }
  return toBrowserMediaSrc(src);
}
