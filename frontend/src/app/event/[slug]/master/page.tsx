'use client';

import { useState, useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { toast } from 'sonner';
import { LayoutGroup } from 'framer-motion';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { LoadingSpinner } from '@/components/shared/loading-spinner';
import { EmptyState } from '@/components/shared/empty-state';
import { GalleryGrid } from '@/components/gallery/gallery-grid';
import { GalleryHeader } from '@/components/gallery/gallery-header';
import { FolderNav } from '@/components/gallery/folder-nav';
import { GallerySkeleton } from '@/components/gallery/gallery-skeleton';
import { ErrorBoundary } from '@/components/shared/error-boundary';
import { AlertCircle } from 'lucide-react';

import { 
  useEventInfo, 
  useMasterAuth, 
  useMasterVerify, 
  useMasterFolders, 
  useMasterPhotos 
} from '@/hooks/use-master-gallery';
import { useFavorites, useToggleFavorite } from '@/hooks/use-couple-favorites';
import { useMasterAuthStore } from '@/stores/master-auth-store';
import { Lock, LogOut } from 'lucide-react';
import { FavoritesFab } from '@/components/couple/favorites-fab';

const PhotoViewer = dynamic(
  () => import('@/components/gallery/photo-viewer').then(mod => mod.PhotoViewer),
  { ssr: false }
);

const phoneRegex = /^[+]?[(]?[0-9]{3}[)]?[-\s.]?[0-9]{3}[-\s.]?[0-9]{4,6}$/im;

const authSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  phone: z.string().regex(phoneRegex, 'Invalid phone number'),
});

const otpSchema = z.object({
  otp: z.string().length(6, 'OTP must be 6 digits'),
});

export default function MasterGalleryPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  
  // Queries
  const { data: infoData, isLoading: infoLoading, error: infoError, refetch: refetchInfo } = useEventInfo(slug);
  
  // Auth state
  const { isAuthenticated, getToken, login, logout } = useMasterAuthStore();
  const [step, setStep] = useState<'auth' | 'otp' | 'gallery'>('auth');
  const [authData, setAuthData] = useState<{ name: string; phone: string } | null>(null);
  
  // Gallery state
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  const eventId = infoData?.event?.id;
  const isAuth = eventId ? isAuthenticated(eventId) : false;
  const token = eventId ? getToken(eventId) : null;

  useEffect(() => {
    if (isAuth) {
      setStep('gallery');
    } else {
      setStep('auth');
    }
  }, [isAuth]);

  // Authenticated Queries
  const { data: folders = [], isLoading: foldersLoading } = useMasterFolders(slug, isAuth ? token : null);
  const { data: photos = [], isLoading: photosLoading, error: photosError, refetch: refetchPhotos } = useMasterPhotos(slug, isAuth ? token : null);
  const { data: favoritePhotos = [] } = useFavorites(slug, isAuth ? token : null);

  const favoritePhotoIds = useMemo(() => new Set(favoritePhotos.map(p => p.id)), [favoritePhotos]);

  // Mutations
  const authMutation = useMasterAuth();
  const verifyMutation = useMasterVerify();
  const toggleFavoriteMutation = useToggleFavorite(slug, isAuth ? token : null);

  // Forms
  const form = useForm<z.infer<typeof authSchema>>({
    resolver: zodResolver(authSchema),
    defaultValues: { name: '', phone: '' },
  });

  const otpForm = useForm<z.infer<typeof otpSchema>>({
    resolver: zodResolver(otpSchema),
    defaultValues: { otp: '' },
  });

  const onAuthSubmit = async (values: z.infer<typeof authSchema>) => {
    try {
      await authMutation.mutateAsync({ slug, data: values });
      setAuthData(values);
      setStep('otp');
      toast.success('OTP sent to your phone');
    } catch (err) {
      toast.error('Failed to send OTP. Please try again.');
    }
  };

  const onOtpSubmit = async (values: z.infer<typeof otpSchema>) => {
    if (!authData || !eventId) return;
    try {
      const { token } = await verifyMutation.mutateAsync({ slug, otp: values.otp });
      login(eventId, { token, name: authData.name, phone: authData.phone });
      toast.success('Successfully logged in');
    } catch (err) {
      toast.error('Invalid OTP. Use 123456 for testing.');
    }
  };

  const displayedPhotos = useMemo(() => {
    let filtered = photos;
    
    if (showFavoritesOnly) {
      filtered = filtered.filter(p => favoritePhotoIds.has(p.id));
    }
    
    if (selectedFolderId) {
      filtered = filtered.filter(p => p.folderId === selectedFolderId);
    }
    
    return filtered;
  }, [selectedFolderId, showFavoritesOnly, photos, favoritePhotoIds]);

  const handlePhotoClick = (index: number) => {
    setViewerIndex(index);
    setViewerOpen(true);
  };

  const handleLogout = () => {
    if (eventId) {
      logout(eventId);
    }
  };

  const photoCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    photos.forEach(p => {
      if (p.folderId) {
        counts[p.folderId] = (counts[p.folderId] || 0) + 1;
      }
    });
    return counts;
  }, [photos]);

  if (infoError) {
    return (
      <div className="dark min-h-screen bg-background text-foreground flex items-center justify-center">
        <EmptyState
          title="Failed to load gallery"
          description={infoError.message}
          icon={<AlertCircle className="h-8 w-8 text-destructive" />}
          action={<Button onClick={() => refetchInfo()}>Try again</Button>}
        />
      </div>
    );
  }

  if (infoLoading) {
    return (
      <div className="dark min-h-screen bg-background text-foreground flex flex-col">
        <div className="h-16 w-full bg-card border-b animate-pulse" />
        <div className="p-6">
          <GallerySkeleton count={10} />
        </div>
      </div>
    );
  }

  if (!infoData?.event) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <EmptyState title="Event Not Found" description="The event you are looking for does not exist." />
      </div>
    );
  }

  const { event, photographer } = infoData;

  if (!event.masterLinkActive) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <EmptyState 
          title="Link Inactive" 
          description="The master gallery link for this event is currently inactive." 
          icon={<Lock className="h-10 w-10 text-muted-foreground" />}
        />
      </div>
    );
  }

  if (step === 'auth' || step === 'otp') {
    return (
      <div className="min-h-screen bg-black text-white flex flex-col items-center justify-center p-4">
        <div className="w-full max-w-md space-y-8 bg-zinc-900 p-8 rounded-xl border border-white/10">
          <div className="text-center">
            {photographer.logoUrl ? (
              <img src={photographer.logoUrl} alt={photographer.studioName} className="h-12 w-auto mx-auto mb-4" />
            ) : (
              <div className="h-12 w-12 rounded-md bg-primary flex items-center justify-center mx-auto mb-4 font-bold text-xl">
                {photographer.studioName.charAt(0)}
              </div>
            )}
            <h2 className="text-2xl font-bold tracking-tight">{event.name}</h2>
            <p className="text-sm text-muted-foreground mt-2">Couple Master Gallery</p>
          </div>

          {step === 'auth' ? (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onAuthSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Your Name</FormLabel>
                      <FormControl>
                        <Input placeholder="John Doe" className="bg-zinc-800 border-zinc-700" {...field} />
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
                        <Input placeholder="+1 234 567 8900" className="bg-zinc-800 border-zinc-700" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" className="w-full" disabled={authMutation.isPending}>
                  {authMutation.isPending ? <LoadingSpinner /> : 'Send OTP'}
                </Button>
              </form>
            </Form>
          ) : (
            <Form {...otpForm}>
              <form onSubmit={otpForm.handleSubmit(onOtpSubmit)} className="space-y-4">
                <div className="text-sm text-center text-zinc-400 mb-4">
                  Enter the 6-digit code sent to {authData?.phone}
                </div>
                <FormField
                  control={otpForm.control}
                  name="otp"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>OTP Code (Try 123456)</FormLabel>
                      <FormControl>
                        <Input placeholder="123456" className="bg-zinc-800 border-zinc-700 text-center tracking-widest text-lg" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex gap-2">
                  <Button type="button" variant="outline" className="w-full" onClick={() => setStep('auth')} disabled={verifyMutation.isPending}>
                    Back
                  </Button>
                  <Button type="submit" className="w-full" disabled={verifyMutation.isPending}>
                    {verifyMutation.isPending ? <LoadingSpinner /> : 'Verify'}
                  </Button>
                </div>
              </form>
            </Form>
          )}
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
    <div className="dark min-h-screen bg-background text-foreground flex flex-col">
      <GalleryHeader event={event} photographer={photographer} />
      
      {/* Logout button injected into header area for convenience */}
      <div className="absolute top-3 right-16 z-20">
        <Button variant="ghost" size="sm" onClick={handleLogout} className="text-muted-foreground hover:text-white">
          <LogOut className="h-4 w-4 mr-2" />
          Logout
        </Button>
      </div>

      <main className="flex-1 w-full max-w-screen-2xl mx-auto flex flex-col">
        <FolderNav
          folders={folders}
          selectedFolderId={selectedFolderId}
          onSelectFolder={setSelectedFolderId}
          photoCounts={photoCounts}
          totalCount={photos.length}
          className="sticky top-16 z-10 bg-background/90 backdrop-blur-sm border-b border-border/10 mb-6"
        />

        {photosError ? (
          <div className="flex-1 flex items-center justify-center p-6">
            <EmptyState
              title="Failed to load photos"
              description={photosError.message}
              icon={<AlertCircle className="h-8 w-8 text-destructive" />}
              action={<Button onClick={() => refetchPhotos()}>Try again</Button>}
            />
          </div>
        ) : foldersLoading || photosLoading ? (
          <div className="flex-1 p-6">
            <GallerySkeleton count={15} />
          </div>
        ) : showFavoritesOnly && displayedPhotos.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState 
              title="No favorites yet" 
              description="Tap the ♡ on any photo to save it here."
            />
          </div>
        ) : (
          <LayoutGroup>
            <GalleryGrid
              photos={displayedPhotos}
              onPhotoClick={handlePhotoClick}
              downloadEnabled={event.downloadEnabled}
              layoutMode="couple"
              favoritePhotoIds={favoritePhotoIds}
              onToggleFavorite={(id) => toggleFavoriteMutation.mutate(id)}
              className="flex-1"
            />
          </LayoutGroup>
        )}
      </main>

      <PhotoViewer
        photos={displayedPhotos}
        currentIndex={viewerIndex}
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        onChangeIndex={setViewerIndex}
        downloadEnabled={event.downloadEnabled}
        favoritePhotoIds={favoritePhotoIds}
        onToggleFavorite={(id) => toggleFavoriteMutation.mutate(id)}
      />

      <FavoritesFab
        count={favoritePhotoIds.size}
        isActive={showFavoritesOnly}
        onClick={() => {
          setShowFavoritesOnly(prev => !prev);
          setSelectedFolderId(null);
        }}
      />
    </div>
    </ErrorBoundary>
  );
}
