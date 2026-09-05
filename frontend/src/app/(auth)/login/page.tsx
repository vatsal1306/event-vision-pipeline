'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
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
import { api, ApiError } from '@/lib/api-client';
import { loginSchema, otpSchema, type LoginFormValues, type OtpFormValues } from '@/lib/auth-schemas';
import { useAuthStore } from '@/stores/auth-store';
import { toast } from 'sonner';

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [registeredPhone, setRegisteredPhone] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const setSession = useAuthStore((state) => state.setSession);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email_or_phone: '',
      password: '',
    },
  });

  const otpForm = useForm<OtpFormValues>({
    resolver: zodResolver(otpSchema),
    defaultValues: {
      otp: '',
    },
  });

  async function onLoginSubmit(data: LoginFormValues) {
    setIsLoading(true);
    try {
      const emailOrPhone = data.email_or_phone.includes('@')
        ? data.email_or_phone
        : data.email_or_phone.startsWith('+')
          ? data.email_or_phone
          : `+91${data.email_or_phone}`;

      const response = await api.login({
        email_or_phone: emailOrPhone,
        password: data.password,
      });

      setRegisteredPhone(response.phone);
      toast.success('OTP sent to your registered phone');
      setStep(2);
    } catch (error: unknown) {
      toast.error(error instanceof ApiError ? error.message : 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  }

  async function onOtpSubmit(data: OtpFormValues) {
    setIsLoading(true);
    try {
      const response = await api.verifyOtp({
        phone: registeredPhone,
        otp: data.otp,
        purpose: 'login',
      });

      setSession(response.photographer, response.access_token, response.refresh_token);
      toast.success('Successfully logged in');
      router.push('/dashboard/events');
    } catch (error: unknown) {
      toast.error(error instanceof ApiError ? error.message : 'Invalid OTP');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <div className="flex flex-col space-y-2 text-center mb-8">
        <h1 className="text-2xl font-bold tracking-tight">
          {step === 1 ? 'Welcome Back' : 'Verify Login'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {step === 1
            ? 'Sign in with your email or phone number and password.'
            : `Enter the 6-digit code sent to ${registeredPhone}`}
        </p>
      </div>

      {step === 1 ? (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onLoginSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="email_or_phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email or Phone</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="studio@example.com or 9876543210"
                      autoComplete="username"
                      disabled={isLoading}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center justify-between">
                    <FormLabel>Password</FormLabel>
                    <Link
                      href="/forgot-password"
                      className="text-sm font-medium text-primary hover:underline"
                      tabIndex={-1}
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <FormControl>
                    <Input
                      placeholder="••••••••"
                      type="password"
                      autoComplete="current-password"
                      disabled={isLoading}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Continue
            </Button>
          </form>
        </Form>
      ) : (
        <Form {...otpForm}>
          <form onSubmit={otpForm.handleSubmit(onOtpSubmit)} className="space-y-4">
            <FormField
              control={otpForm.control}
              name="otp"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>One-Time Password</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="123456"
                      maxLength={6}
                      className="text-center text-lg tracking-[0.5em]"
                      disabled={isLoading}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Log In
            </Button>

            <Button
              type="button"
              variant="ghost"
              className="w-full"
              disabled={isLoading}
              onClick={() => setStep(1)}
            >
              Back to login
            </Button>
          </form>
        </Form>
      )}

      {step === 1 && (
        <div className="mt-6 text-center text-sm">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="font-semibold text-primary hover:underline">
            Sign up
          </Link>
        </div>
      )}
    </>
  );
}
