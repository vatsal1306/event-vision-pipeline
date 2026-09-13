import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  resolveProxyUrl,
  shouldBypassImageOptimization,
  toBrowserMediaSrc,
} from '@/lib/media-url';

describe('shouldBypassImageOptimization', () => {
  it('should bypass the optimizer for signed API preview URLs', () => {
    const src =
      'https://spotme.hpklabs.ai/api/v1/events/abc/photos/def/preview?expires=1&sig=deadbeef';
    expect(shouldBypassImageOptimization(src)).toBe(true);
  });

  it('should bypass the optimizer for same-origin relative preview paths', () => {
    expect(
      shouldBypassImageOptimization('/api/v1/events/abc/photos/def/preview?expires=1&sig=abc')
    ).toBe(true);
  });

  it('should bypass the optimizer for local API hosts', () => {
    expect(
      shouldBypassImageOptimization('http://localhost:8000/api/v1/events/a/photos/b/preview?expires=1&sig=x')
    ).toBe(true);
  });

  it('should keep optimization for public mock CDNs', () => {
    expect(shouldBypassImageOptimization('https://picsum.photos/seed/1/800/600')).toBe(false);
  });
});

describe('toBrowserMediaSrc', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('should rewrite configured same-host API URLs to relative paths', () => {
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://spotme.hpklabs.ai');
    vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'https://spotme.hpklabs.ai');
    const src =
      'https://spotme.hpklabs.ai/api/v1/events/abc/photos/def/preview?expires=1&sig=deadbeef';
    expect(toBrowserMediaSrc(src)).toBe(
      '/api/v1/events/abc/photos/def/preview?expires=1&sig=deadbeef'
    );
  });

  it('should leave a different-origin API URL absolute', () => {
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://spotme.hpklabs.ai');
    vi.stubEnv('NEXT_PUBLIC_API_BASE_URL', 'https://spotme.hpklabs.ai');
    const src = 'https://api.example.com/api/v1/events/abc/photos/def/preview?expires=1&sig=x';
    expect(toBrowserMediaSrc(src)).toBe(src);
  });

  it('should pass through nullish proxy URLs', () => {
    expect(resolveProxyUrl(null)).toBeNull();
    expect(resolveProxyUrl(undefined)).toBeNull();
    expect(resolveProxyUrl('')).toBe('');
  });
});
