export const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/tiff'];

export function isValidFileType(file: File): boolean {
  if (SUPPORTED_IMAGE_TYPES.includes(file.type)) return true;
  
  // fallback check for extension if type is empty (common for heic on some platforms)
  const ext = file.name.split('.').pop()?.toLowerCase();
  return ext ? ['jpg', 'jpeg', 'png', 'webp', 'heic', 'tiff'].includes(ext) : false;
}

export function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond === 0) return '0 B/s';
  const k = 1024;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  const i = Math.floor(Math.log(bytesPerSecond) / Math.log(k));
  return parseFloat((bytesPerSecond / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '--';
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainingMins = mins % 60;
  return `${hours}h ${remainingMins}m`;
}
