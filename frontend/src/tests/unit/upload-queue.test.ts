import { describe, it, expect } from 'vitest';
import { isValidFileType, formatSpeed, formatTime, SUPPORTED_IMAGE_TYPES } from '@/lib/upload/file-utils';

describe('Upload File Utils', () => {
  describe('isValidFileType', () => {
    it('should return true for supported image types', () => {
      const validFile = new File([''], 'photo.jpg', { type: 'image/jpeg' });
      expect(isValidFileType(validFile)).toBe(true);
    });

    it('should return false for unsupported types', () => {
      const invalidFile = new File([''], 'document.pdf', { type: 'application/pdf' });
      expect(isValidFileType(invalidFile)).toBe(false);
    });

    it('should fallback to extension check if type is empty (e.g., HEIC)', () => {
      const heicFile = new File([''], 'photo.heic', { type: '' });
      expect(isValidFileType(heicFile)).toBe(true);
    });
  });

  describe('formatSpeed', () => {
    it('should format bytes per second correctly', () => {
      expect(formatSpeed(0)).toBe('0 B/s');
      expect(formatSpeed(1024)).toBe('1 KB/s');
      expect(formatSpeed(1024 * 1024)).toBe('1 MB/s');
      expect(formatSpeed(1024 * 1024 * 5.5)).toBe('5.5 MB/s');
    });
  });

  describe('formatTime', () => {
    it('should format seconds into readable time', () => {
      expect(formatTime(45)).toBe('45s');
      expect(formatTime(120)).toBe('2m');
      expect(formatTime(3660)).toBe('1h 1m');
      expect(formatTime(-1)).toBe('--');
    });
  });
});
