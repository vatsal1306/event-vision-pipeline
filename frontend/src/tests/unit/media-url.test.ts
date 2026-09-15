import { afterEach, describe, expect, it, vi } from 'vitest';
import { extractApiMediaPath, resolveProxyUrl, toBrowserMediaSrc } from '@/lib/media-url';

describe('extractApiMediaPath', () => {
  it('should keep a relative API path', () => {
    expect(extractApiMediaPath('/api/v1/events/a/photos/b/preview?expires=1&sig=x')).toBe(
      '/api/v1/events/a/photos/b/preview?expires=1&sig=x'
    );
  });

  it('should strip any host from an API preview URL', () => {
    expect(
      extractApiMediaPath('http://localhost:8000/api/v1/events/a/photos/b/preview?expires=1&sig=x')
    ).toBe('/api/v1/events/a/photos/b/preview?expires=1&sig=x');
  });

  it('should ignore non-API URLs', () => {
    expect(extractApiMediaPath('https://picsum.photos/seed/1/800/600')).toBeNull();
  });
});

describe('toBrowserMediaSrc', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('should use a relative path when the app and API share a public host', () => {
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://spotme.hpklabs.ai');
    vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'https://spotme.hpklabs.ai');
    expect(
      toBrowserMediaSrc('http://localhost:8000/api/v1/events/abc/photos/def/preview?expires=1&sig=deadbeef')
    ).toBe('/api/v1/events/abc/photos/def/preview?expires=1&sig=deadbeef');
  });

  it('should prefix the local API origin when frontend and API ports differ', () => {
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'http://localhost:3000');
    vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'http://localhost:8000');
    expect(
      toBrowserMediaSrc('http://backend:8000/api/v1/events/abc/photos/def/preview?expires=1&sig=x')
    ).toBe('http://localhost:8000/api/v1/events/abc/photos/def/preview?expires=1&sig=x');
  });

  it('should pass through nullish proxy URLs', () => {
    expect(resolveProxyUrl(null)).toBeNull();
    expect(resolveProxyUrl(undefined)).toBeNull();
    expect(resolveProxyUrl('')).toBe('');
  });
});
