'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
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
import { api } from '@/lib/api-client';

const forgotPasswordSchema = z.object({
  email_or_phone: z.string().min(3, 'Email or phone is required.'),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export default function ForgotPasswordPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email_or_phone: '',
    },
  });

  async function onSubmit(data: ForgotPasswordFormValues) {
    setIsLoading(true);
    try {
      const emailOrPhone = data.email_or_phone.includes('@')
        ? data.email_or_phone
        : data.email_or_phone.startsWith('+')
          ? data.email_or_phone
          : `+91${data.email_or_phone}`;

      await api.forgotPassword({
        email_or_phone: emailOrPhone,
      });
    } catch {
      // Always show success to avoid account enumeration.
    } finally {
      setIsSubmitted(true);
      setIsLoading(false);
    }
  }

  if (isSubmitted) {
    return (
      <div className="flex flex-col items-center justify-center space-y-4 text-center">
        <CheckCircle2 className="h-12 w-12 text-primary" />
        <h1 className="text-2xl font-bold tracking-tight">Check your phone</h1>
        <p className="text-sm text-muted-foreground mb-4">
          If an account exists, we sent an OTP to the registered phone number for{' '}
          <span className="font-medium text-foreground">{form.getValues('email_or_phone')}</span>.
        </p>
        <Button asChild className="w-full">
          <Link href="/reset-password">Enter OTP and reset password</Link>
        </Button>
        <Button asChild variant="ghost" className="w-full">
          <Link href="/login">Return to log in</Link>
        </Button>
      </div>
    );
  }

  return (
    <>
      <div className="flex flex-col space-y-2 text-center mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Forgot Password</h1>
        <p className="text-sm text-muted-foreground">
          Enter your email or phone number and we&apos;ll send an OTP to your registered phone.
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

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Send OTP
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
