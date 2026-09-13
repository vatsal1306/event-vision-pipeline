/**
 * Detect when the browser cannot reach tusd so we can fall back to FastAPI ingest.
 */
export function isTusdUnreachableError(error: unknown): boolean {
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  return (
    message.includes('failed to fetch') ||
    message.includes('networkerror') ||
    message.includes('load failed') ||
    message.includes('err_connection_refused') ||
    message.includes('failed to connect')
  );
}

/**
 * Cheap OPTIONS probe. Any HTTP response means tusd is up; network errors mean it is not.
 */
export async function isTusdReachable(endpoint: string, timeoutMs = 1500): Promise<boolean> {
  if (!endpoint) {
    return false;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    await fetch(endpoint, { method: 'OPTIONS', signal: controller.signal });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
