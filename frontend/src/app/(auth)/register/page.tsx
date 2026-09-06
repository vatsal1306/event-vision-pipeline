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
import { api, ApiError } from '@/lib/api-client';
import { registerSchema, type RegisterFormValues } from '@/lib/auth-schemas';
import { useAuthStore } from '@/stores/auth-store';
import { toast } from 'sonner';

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
      await api.register({
        studioName: data.studioName,
        email: data.email,
        password: data.password,
        mobile: `+91${data.mobile}`,
      });
      toast.success('OTP sent to your mobile number');
      setStep(2);
    } catch (error: unknown) {
      toast.error(error instanceof ApiError ? error.message : 'Failed to register');
    } finally {
      setIsLoading(false);
    }
  }

  async function onOtpSubmit(data: OtpFormValues) {
    setIsLoading(true);
    try {
      const response = await api.verifyOtp({
        phone: `+91${form.getValues('mobile')}`,
        code: data.code,
      });

      setTokens(response.accessToken, response.refreshToken);
      toast.success('Account created successfully');
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
