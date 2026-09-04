import { describe, it, expect } from 'vitest';
import { loginSchema, registerSchema } from '@/lib/auth-schemas';
import { loginSchema } from '@/app/(auth)/login/page';
import { registerSchema } from '@/app/(auth)/register/page';
import { authSchema as guestAuthSchema } from '@/components/guest/otp-form';

describe('Auth Schemas', () => {
  describe('loginSchema', () => {
    it('should validate a correct email and password', () => {
      const result = loginSchema.safeParse({ email: 'test@example.com', password: 'password123' });
      expect(result.success).toBe(true);
    });

    it('should fail on invalid email', () => {
      const result = loginSchema.safeParse({ email: 'invalid-email', password: 'password123' });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Please enter a valid email address.');
      }
    });

    it('should fail on empty password', () => {
      const result = loginSchema.safeParse({ email: 'test@example.com', password: '' });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Password is required.');
      }
    });
  });

  describe('registerSchema', () => {
    it('should validate a correct registration payload', () => {
      const result = registerSchema.safeParse({
        studioName: 'My Studio',
        email: 'test@example.com',
        password: 'Password123!',
        confirmPassword: 'Password123!',
        mobile: '1234567890',
      });
      expect(result.success).toBe(true);
    });

    it('should fail if password is too short', () => {
      const result = registerSchema.safeParse({
        studioName: 'My Studio',
        email: 'test@example.com',
        password: 'pass',
        confirmPassword: 'pass',
        mobile: '1234567890',
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Password must be at least 8 characters.');
      }
    });
  });

  describe('guestAuthSchema', () => {
    it('should validate correct name and phone', () => {
      const result = guestAuthSchema.safeParse({ name: 'John Doe', phone: '+1234567890' });
      expect(result.success).toBe(true);
    });

    it('should fail on invalid phone number', () => {
      const result = guestAuthSchema.safeParse({ name: 'John', phone: 'invalid-phone' });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toBe('Invalid phone number');
      }
    });
  });
});
