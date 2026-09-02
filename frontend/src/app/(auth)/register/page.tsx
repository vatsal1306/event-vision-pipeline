'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api-client';
import { useAuthStore } from '@/stores/auth-store';
import { toast } from 'sonner';

const registerSchema = z.object({
  studioName: z.string().min(2, 'Studio name must be at least 2 characters.'),
  email: z.string().email('Please enter a valid email address.'),
  password: z
    .string()
    .min(8, 'Password must be at least 8 characters.')
    .regex(/[A-Z]/, 'Must contain at least one uppercase letter.')
    .regex(/[a-z]/, 'Must contain at least one lowercase letter.')
    .regex(/[0-9]/, 'Must contain at least one number.'),
  confirmPassword: z.string(),
  mobile: z.string().regex(/^\d{10}$/, 'Must be a valid 10-digit mobile number.'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ['confirmPassword'],
});

type RegisterFormValues = z.infer<typeof registerSchema>;

const otpSchema = z.object({
  code: z.string().length(6, 'OTP must be exactly 6 digits.'),
});

type OtpFormValues = z.infer<typeof otpSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [isLoading, setIsLoading] = useState(false);
  const setTokens = useAuthStore((state) => state.setTokens);

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      studioName: '',
      email: '',
      password: '',
      confirmPassword: '',
      mobile: '',
    },
  });

  const otpForm = useForm<OtpFormValues>({
    resolver: zodResolver(otpSchema),
    defaultValues: {
      code: '',
    },
  });

  async function onRegisterSubmit(data: RegisterFormValues) {
    setIsLoading(true);
    try {
      await apiClient.post('/auth/register', {
        studioName: data.studioName,
        email: data.email,
        password: data.password,
        mobile: `+91${data.mobile}`,
      });
      toast.success('OTP sent to your mobile number');
      setStep(2);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to register');
    } finally {
      setIsLoading(false);
    }
  }

  async function onOtpSubmit(data: OtpFormValues) {
    setIsLoading(true);
    try {
      const response = await apiClient.post<{ accessToken: string; refreshToken: string }>('/auth/verify-otp', {
        code: data.code,
      });

      setTokens(response.accessToken, response.refreshToken);
      toast.success('Account created successfully');
      router.push('/dashboard/events');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Invalid OTP');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <div className="flex flex-col space-y-2 text-center mb-8">
        <h1 className="text-2xl font-bold tracking-tight">
          {step === 1 ? 'Create Your Account' : 'Verify Mobile Number'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {step === 1
            ? 'Start delivering photos instantly to your clients.'
            : `We sent a 6-digit code to +91 ${form.getValues('mobile')}`}
        </p>
      </div>

      {step === 1 ? (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onRegisterSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="studioName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Studio Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Awesome Photography" disabled={isLoading} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input placeholder="studio@example.com" type="email" autoComplete="email" disabled={isLoading} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input placeholder="••••••••" type="password" autoComplete="new-password" disabled={isLoading} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="confirmPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirm Password</FormLabel>
                    <FormControl>
                      <Input placeholder="••••••••" type="password" autoComplete="new-password" disabled={isLoading} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="mobile"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Mobile Number</FormLabel>
                  <FormControl>
                    <div className="flex">
                      <div className="flex items-center justify-center rounded-l-md border border-r-0 border-input bg-muted px-3 text-sm text-muted-foreground">
                        +91
                      </div>
                      <Input placeholder="9876543210" type="tel" className="rounded-l-none" disabled={isLoading} {...field} />
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" className="w-full mt-2" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Send OTP to Mobile
            </Button>
          </form>
        </Form>
      ) : (
        <Form {...otpForm}>
          <form onSubmit={otpForm.handleSubmit(onOtpSubmit)} className="space-y-4">
            <FormField
              control={otpForm.control}
              name="code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>One-Time Password</FormLabel>
                  <FormControl>
                    <Input placeholder="123456" maxLength={6} className="text-center text-lg tracking-[0.5em]" disabled={isLoading} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Account
            </Button>
            
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              disabled={isLoading}
              onClick={() => setStep(1)}
            >
              Back to registration
            </Button>
          </form>
        </Form>
      )}

      {step === 1 && (
        <div className="mt-6 text-center text-sm">
          Already have an account?{' '}
          <Link href="/login" className="font-semibold text-primary hover:underline">
            Log in
          </Link>
        </div>
      )}
    </>
  );
}
