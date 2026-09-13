import { describe, expect, it } from 'vitest';
import { resolveApiBaseUrl } from '@/lib/resolve-api-base-url';

describe('resolveApiBaseUrl', () => {
  it('should keep a host-only origin used in local development', () => {
    expect(resolveApiBaseUrl('http://localhost:8000')).toBe('http://localhost:8000');
  });

  it('should strip a trailing /api used as a reverse-proxy prefix', () => {
    expect(resolveApiBaseUrl('https://spotme.hpklabs.ai/api')).toBe('https://spotme.hpklabs.ai');
  });

  it('should strip trailing slashes before joining /api/v1 paths', () => {
    expect(resolveApiBaseUrl('https://spotme.hpklabs.ai/api/')).toBe('https://spotme.hpklabs.ai');
    expect(resolveApiBaseUrl('https://spotme.hpklabs.ai/')).toBe('https://spotme.hpklabs.ai');
  });

  it('should treat a missing value as an empty same-origin base', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('');
    expect(resolveApiBaseUrl('  ')).toBe('');
  });
});
