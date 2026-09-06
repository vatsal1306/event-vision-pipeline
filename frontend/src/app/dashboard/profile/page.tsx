'use client';

import { useState, useRef, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { User, Settings, Image as ImageIcon, HardDrive, Upload, X } from 'lucide-react';
import Image from 'next/image';

import { useProfile, useUpdateProfile, useUploadLogo, useUploadWatermark } from '@/hooks/use-profile';
import { formatBytes } from '@/lib/utils';
import { WatermarkPreview } from '@/components/dashboard/watermark-preview';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';

const profileSchema = z.object({
  studioName: z.string().min(2, 'Studio name is required'),
  email: z.string().email('Invalid email address'),
  phone: z.string().min(10, 'Phone number must be at least 10 digits'),
});

type ProfileFormValues = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const { data: profile, isLoading, isError, refetch } = useProfile();
  const updateProfile = useUpdateProfile();
  const uploadLogo = useUploadLogo();
  const uploadWatermark = useUploadWatermark();

  const [localLogoPreview, setLocalLogoPreview] = useState<string | null>(null);
  const [localWatermarkPreview, setLocalWatermarkPreview] = useState<string | null>(null);

  const logoInputRef = useRef<HTMLInputElement>(null);
  const watermarkInputRef = useRef<HTMLInputElement>(null);

  const form = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      studioName: '',
      email: '',
      phone: '',
    },
  });

  useEffect(() => {
    if (profile) {
      form.reset({
        studioName: profile.studioName,
        email: profile.email,
        phone: profile.phone,
      });
      if (profile.logoUrl && !localLogoPreview) setLocalLogoPreview(profile.logoUrl);
      if (profile.watermarkUrl && !localWatermarkPreview) setLocalWatermarkPreview(profile.watermarkUrl);
    }
  }, [profile, form, localLogoPreview, localWatermarkPreview]);

  // Cleanup object URLs to avoid memory leaks
  useEffect(() => {
    return () => {
      if (localLogoPreview && localLogoPreview.startsWith('blob:')) {
        URL.revokeObjectURL(localLogoPreview);
      }
      if (localWatermarkPreview && localWatermarkPreview.startsWith('blob:')) {
        URL.revokeObjectURL(localWatermarkPreview);
      }
    };
  }, [localLogoPreview, localWatermarkPreview]);

  if (isLoading) {
    return <div className="p-8 text-muted-foreground">Loading profile...</div>;
  }

  if (isError || !profile) {
    return (
      <div className="p-8 flex flex-col items-start gap-4">
        <p className="text-destructive">Failed to load profile.</p>
        <Button variant="outline" onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  const onSubmit = (data: ProfileFormValues) => {
    updateProfile.mutate(data);
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (localLogoPreview && localLogoPreview.startsWith('blob:')) {
      URL.revokeObjectURL(localLogoPreview);
    }

    // Create local preview instantly
    const previewUrl = URL.createObjectURL(file);
    setLocalLogoPreview(previewUrl);

    // Trigger upload
    uploadLogo.mutate(file, {
      onSuccess: () => {
        // Once successful, we could optionally clear the local preview if the mock returned a real URL, 
        // but here we just rely on query invalidation updating the profile data.
      }
    });
  };

  const handleWatermarkUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (file.type !== 'image/png') {
      toast.error('Watermark must be a PNG image');
      return;
    }

    if (localWatermarkPreview && localWatermarkPreview.startsWith('blob:')) {
      URL.revokeObjectURL(localWatermarkPreview);
    }

    // Create local preview instantly
    const previewUrl = URL.createObjectURL(file);
    setLocalWatermarkPreview(previewUrl);

    // Trigger upload
    uploadWatermark.mutate(file);
  };

  const removeLocalLogo = () => {
    if (localLogoPreview && localLogoPreview.startsWith('blob:')) {
      URL.revokeObjectURL(localLogoPreview);
    }
    setLocalLogoPreview(null);
    updateProfile.mutate({ logoUrl: null });
  };

  const removeLocalWatermark = () => {
    if (localWatermarkPreview && localWatermarkPreview.startsWith('blob:')) {
      URL.revokeObjectURL(localWatermarkPreview);
    }
    setLocalWatermarkPreview(null);
    updateProfile.mutate({ watermarkUrl: null });
  };

  const storagePercentage = Math.min(100, (profile.storageUsedBytes / profile.storageLimitBytes) * 100);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-display font-semibold tracking-tight text-foreground">Studio Profile</h1>
        <p className="text-muted-foreground mt-2">Manage your studio identity, branding, and storage limits.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Left Column: Form & Storage */}
        <div className="space-y-8">
          {/* Form */}
          <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <User className="h-5 w-5 text-muted-foreground" />
                Contact Info
              </h3>
            </div>
            <div className="p-6">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                  <FormField
                    control={form.control}
                    name="studioName"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Studio Name</FormLabel>
                        <FormControl>
                          <Input placeholder="Vatsal Studio" {...field} />
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
                        <FormLabel>Email Address</FormLabel>
                        <FormControl>
                          <Input placeholder="vatsal@example.com" type="email" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Phone Number</FormLabel>
                        <FormControl>
                          <Input placeholder="+919876543210" type="tel" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button type="submit" disabled={updateProfile.isPending}>
                    {updateProfile.isPending ? 'Saving...' : 'Save Changes'}
                  </Button>
                </form>
              </Form>
            </div>
          </div>

          {/* Storage */}
          <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <HardDrive className="h-5 w-5 text-muted-foreground" />
                Storage Usage
              </h3>
            </div>
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Active Storage</span>
                <span className="text-sm font-mono text-muted-foreground">
                  {formatBytes(profile.storageUsedBytes)} / {formatBytes(profile.storageLimitBytes)}
                </span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{ width: `${storagePercentage}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Your current plan includes 100GB of active event storage. Archived events do not count against this limit.
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: Branding (Logo & Watermark) */}
        <div className="space-y-8">
          {/* Logo Upload */}
          <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <ImageIcon className="h-5 w-5 text-muted-foreground" />
                Studio Logo
              </h3>
            </div>
            <div className="p-6 flex flex-col items-center gap-4">
              <div className="relative w-32 h-32 rounded-full overflow-hidden bg-muted border-2 border-dashed flex items-center justify-center">
                {localLogoPreview ? (
                  <>
                    <Image src={localLogoPreview} alt="Logo" fill className="object-cover" unoptimized />
                    <button 
                      onClick={removeLocalLogo}
                      className="absolute top-1 right-1 bg-background/80 p-1 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors"
                      title="Remove Logo"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </>
                ) : (
                  <ImageIcon className="h-8 w-8 text-muted-foreground/50" />
                )}
              </div>
              <div className="flex flex-col items-center gap-2">
                <Input 
                  type="file" 
                  accept="image/jpeg,image/png,image/webp" 
                  className="hidden" 
                  ref={logoInputRef}
                  onChange={handleLogoUpload}
                />
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => logoInputRef.current?.click()}
                  disabled={uploadLogo.isPending}
                >
                  <Upload className="h-4 w-4 mr-2" />
                  {uploadLogo.isPending ? 'Uploading...' : 'Upload Logo'}
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  Recommended: 400x400px (JPG/PNG). Displayed in guest galleries.
                </p>
              </div>
            </div>
          </div>

          {/* Watermark Upload */}
          <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
            <div className="p-6 border-b">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <ImageIcon className="h-5 w-5 text-muted-foreground" />
                Photo Watermark
              </h3>
            </div>
            <div className="p-6 space-y-4">
              <WatermarkPreview watermarkSrc={localWatermarkPreview} />
              
              <div className="flex flex-col items-start gap-2">
                <Input 
                  type="file" 
                  accept="image/png" 
                  className="hidden" 
                  ref={watermarkInputRef}
                  onChange={handleWatermarkUpload}
                />
                <div className="flex items-center gap-2 w-full">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => watermarkInputRef.current?.click()}
                    disabled={uploadWatermark.isPending}
                    className="flex-1"
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    {uploadWatermark.isPending ? 'Uploading...' : 'Upload Watermark'}
                  </Button>
                  {localWatermarkPreview && (
                    <Button 
                      variant="destructive" 
                      size="sm"
                      onClick={removeLocalWatermark}
                      disabled={updateProfile.isPending}
                      title="Remove Watermark"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Must be a transparent PNG. Overlaid automatically in the bottom-right corner of web-optimized downloads.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
