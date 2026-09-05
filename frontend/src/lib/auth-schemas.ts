import { z } from 'zod';

const passwordSchema = z
  .string()
  .min(8, 'Password must be at least 8 characters.')
  .max(16, 'Password must be at most 16 characters.')
  .regex(/[A-Z]/, 'Must contain at least one uppercase letter.')
  .regex(/[a-z]/, 'Must contain at least one lowercase letter.')
  .regex(/[0-9]/, 'Must contain at least one number.')
  .regex(/[^A-Za-z0-9]/, 'Must contain at least one special character.');

export const loginSchema = z.object({
  email_or_phone: z.string().min(3, 'Email or phone is required.'),
  password: z.string().min(1, 'Password is required.'),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    studioName: z.string().min(2, 'Studio name must be at least 2 characters.'),
    email: z.string().email('Please enter a valid email address.'),
    password: passwordSchema,
    confirmPassword: z.string(),
    mobile: z.string().regex(/^\d{10}$/, 'Must be a valid 10-digit mobile number.'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  });

export type RegisterFormValues = z.infer<typeof registerSchema>;

export const otpSchema = z.object({
  otp: z.string().length(6, 'OTP must be exactly 6 digits.'),
});

export type OtpFormValues = z.infer<typeof otpSchema>;

export const resetPasswordSchema = z
  .object({
    email_or_phone: z.string().min(3, 'Email or phone is required.'),
    otp: z.string().length(6, 'OTP must be exactly 6 digits.'),
    new_password: passwordSchema,
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords don't match",
    path: ['confirm_password'],
  });

export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;
