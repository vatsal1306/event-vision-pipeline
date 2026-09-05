'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2, CheckCircle2 } from 'lucide-react';

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
import { resetPasswordSchema, type ResetPasswordFormValues } from '@/lib/auth-schemas';

export default function ResetPasswordPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      email_or_phone: '',
      otp: '',
      new_password: '',
      confirm_password: '',
    },
  });

  async function onSubmit(data: ResetPasswordFormValues) {
    setIsLoading(true);
    try {
      const emailOrPhone = data.email_or_phone.includes('@')
        ? data.email_or_phone
        : data.email_or_phone.startsWith('+')
          ? data.email_or_phone
          : `+91${data.email_or_phone}`;

      await api.resetPassword({
        email_or_phone: emailOrPhone,
        otp: data.otp,
        new_password: data.new_password,
      });
      setIsSubmitted(true);
    } catch (error: unknown) {
      form.setError('otp', {
        message: error instanceof ApiError ? error.message : 'Failed to reset password',
      });
    } finally {
      setIsLoading(false);
    }
  }

  if (isSubmitted) {
    return (
      <div className="flex flex-col items-center justify-center space-y-4 text-center">
        <CheckCircle2 className="h-12 w-12 text-primary" />
        <h1 className="text-2xl font-bold tracking-tight">Password updated</h1>
        <p className="text-sm text-muted-foreground mb-4">
          Your password has been reset. You can now log in with your new password.
        </p>
        <Button asChild className="w-full">
          <Link href="/login">Return to log in</Link>
        </Button>
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col space-y-2 text-center mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Reset Password</h1>
        <p className="text-sm text-muted-foreground">
          Enter the OTP sent to your registered phone and choose a new password.
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="email_or_phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email or Phone</FormLabel>
                <FormControl>
                  <Input placeholder="studio@example.com or 9876543210" disabled={isLoading} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
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

          <FormField
            control={form.control}
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>New Password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" disabled={isLoading} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirm Password</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" disabled={isLoading} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Reset Password
          </Button>
        </form>
      </Form>

      <div className="mt-6 text-center text-sm">
        <Link href="/login" className="font-semibold text-primary hover:underline">
          Back to log in
        </Link>
      </div>
    </>
  );
}
