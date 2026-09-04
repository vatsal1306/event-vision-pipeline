import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';

const phoneRegex = /^[+]?[(]?[0-9]{3}[)]?[-\s.]?[0-9]{3}[-\s.]?[0-9]{4,6}$/im;

const authSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  phone: z.string().regex(phoneRegex, 'Invalid phone number'),
});

const otpSchema = z.object({
  otp: z.string().length(6, 'OTP must be 6 digits'),
});

interface OtpFormProps {
  onSendOtp: (data: { name: string; phone: string }) => Promise<void>;
  onVerifyOtp: (otp: string) => Promise<void>;
  isLoading: boolean;
}

export function OtpForm({ onSendOtp, onVerifyOtp, isLoading }: OtpFormProps) {
  const [step, setStep] = useState<'auth' | 'otp'>('auth');

  const authForm = useForm<z.infer<typeof authSchema>>({
    resolver: zodResolver(authSchema),
    defaultValues: { name: '', phone: '' },
  });

  const otpForm = useForm<z.infer<typeof otpSchema>>({
    resolver: zodResolver(otpSchema),
    defaultValues: { otp: '' },
  });

  const handleAuthSubmit = async (values: z.infer<typeof authSchema>) => {
    await onSendOtp(values);
    setStep('otp');
  };

  const handleOtpSubmit = async (values: z.infer<typeof otpSchema>) => {
    await onVerifyOtp(values.otp);
  };

  if (step === 'auth') {
    return (
      <Form {...authForm}>
        <form onSubmit={authForm.handleSubmit(handleAuthSubmit)} className="space-y-4">
          <FormField
            control={authForm.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-zinc-400">Name</FormLabel>
                <FormControl>
                  <Input 
                    placeholder="Enter your name" 
                    className="bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 h-12" 
                    {...field} 
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={authForm.control}
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-zinc-400">Mobile</FormLabel>
                <FormControl>
                  <Input 
                    placeholder="Enter your mobile number" 
                    type="tel"
                    className="bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 h-12" 
                    {...field} 
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button 
            type="submit" 
            className="w-full h-12 text-base mt-2" 
            disabled={isLoading}
          >
            {isLoading ? 'Sending...' : 'Send OTP'}
          </Button>
        </form>
      </Form>
    );
  }

  return (
    <Form {...otpForm}>
      <form onSubmit={otpForm.handleSubmit(handleOtpSubmit)} className="space-y-4">
        <FormField
          control={otpForm.control}
          name="otp"
          render={({ field }) => (
            <FormItem>
              <FormLabel className="text-zinc-400">OTP</FormLabel>
              <FormControl>
                <Input 
                  placeholder="Enter 6-digit OTP" 
                  maxLength={6}
                  className="bg-zinc-800/50 border-zinc-700 text-white placeholder:text-zinc-500 text-center text-lg tracking-[0.5em] h-14" 
                  {...field} 
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button 
          type="submit" 
          className="w-full h-12 text-base mt-2" 
          disabled={isLoading}
        >
          {isLoading ? 'Verifying...' : 'Verify OTP'}
        </Button>
        <button
          type="button"
          onClick={() => setStep('auth')}
          className="w-full text-sm text-zinc-400 hover:text-white mt-4"
        >
          Change phone number
        </button>
      </form>
    </Form>
  );
}
