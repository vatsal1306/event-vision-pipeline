'use client';

import { useState, useEffect, useMemo } from 'react';
import { useEventInfo } from '@/hooks/use-master-gallery';
import { useGuestAuth, useGuestVerify, useSubmitSelfie, useGuestPhotos, useGuestHighlights } from '@/hooks/use-guest-gallery';
import { useGuestAuthStore } from '@/stores/guest-auth-store';
import { LoadingSpinner } from '@/components/shared/loading-spinner';
import { EmptyState } from '@/components/shared/empty-state';
import { GalleryNotReady } from '@/components/shared/gallery-not-ready';
import { Lock } from 'lucide-react';
import { OtpForm } from '@/components/guest/otp-form';
import { SelfieCapture } from '@/components/guest/selfie-capture';
import { ProcessingScreen } from '@/components/guest/processing-screen';
import { PersonalizedGallery } from '@/components/guest/personalized-gallery';
import { GallerySkeleton } from '@/components/gallery/gallery-skeleton';
import { ErrorBoundary } from '@/components/shared/error-boundary';
import { getInitials } from '@/lib/utils';
import { isGalleryReady } from '@/lib/face-processing';
import { guestSelfieFailureCopy, canProceedToGallery } from '@/lib/guest-selfie';
import { getPaginatedTotal } from '@/lib/pagination';
import { toast } from 'sonner';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

const Throw = ({ error }: { error: Error }) => { throw error; };

type FlowStep = 'auth' | 'selfie' | 'processing' | 'gallery';

export default function GuestGalleryPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  
  // Queries
  const { data: infoData, isLoading: infoLoading, error: infoError, refetch: refetchInfo } = useEventInfo(slug);
  
  // Auth state
  const { guestSession, sessionToken, needsSelfie, isVerified, setGuestSession, clearGuestSession } = useGuestAuthStore();
  const [step, setStep] = useState<FlowStep>('auth');
  const [authData, setAuthData] = useState<{ name: string; phone: string } | null>(null);
  
  // Ensure we show the correct step based on stored state
  useEffect(() => {
    if (isVerified && sessionToken && guestSession) {
      if (infoData?.event && guestSession.eventId !== infoData.event.id) {
        clearGuestSession();
        setStep('auth');
        return;
      }
      if (needsSelfie) {
        setStep('selfie');
      } else {
        setStep('gallery');
      }
    } else {
      setStep('auth');
    }
  }, [isVerified, sessionToken, needsSelfie, guestSession, infoData?.event, clearGuestSession]);

  // Authenticated Queries
  const photosQuery = useGuestPhotos(slug, !needsSelfie && isVerified ? sessionToken : null);
  const photosData = useMemo(() => photosQuery.data?.pages.flatMap(page => page.items) ?? [], [photosQuery.data]);
  const photosLoading = photosQuery.isLoading;
  const photosError = photosQuery.error;
  const refetchPhotos = photosQuery.refetch;

  const highlightsQuery = useGuestHighlights(slug, isVerified ? sessionToken : null);
  const highlightsData = useMemo(() => highlightsQuery.data?.pages.flatMap(page => page.items) ?? [], [highlightsQuery.data]);
  const highlightsLoading = highlightsQuery.isLoading;
  const highlightsError = highlightsQuery.error;
  const refetchHighlights = highlightsQuery.refetch;

  // Mutations
  const authMutation = useGuestAuth();
  const verifyMutation = useGuestVerify();
  const selfieMutation = useSubmitSelfie();

  const handleSendOtp = async (data: { name: string; phone: string }) => {
    try {
      await authMutation.mutateAsync({ slug, data });
      setAuthData(data);
      toast.success('OTP sent to your phone');
    } catch (err) {
      toast.error('Failed to send OTP. Please try again.');
      throw err;
    }
  };

  const handleVerifyOtp = async (otp: string) => {
    if (!authData || !infoData?.event) return;
    try {
      const { access_token, needs_selfie } = await verifyMutation.mutateAsync({ slug, name: authData.name, phone: authData.phone, otp });
      // Use the returned needs_selfie status
      setGuestSession(
        { 
          id: `guest-${Date.now()}`,
          eventId: infoData.event.id,
          name: authData.name,
          phone: authData.phone,
          phoneVerified: true,
          selfieUrl: null,
          matchedClusterIds: [],
          matchedPhotoCount: 0,
          status: 'verified',
          createdAt: new Date().toISOString(),
        },
        access_token,
        needs_selfie
      );
      toast.success('Successfully logged in');
    } catch (err) {
      toast.error('Invalid OTP. Please check the code and try again.');
    }
  };

  const handleSelfieCapture = async (imageBlob: Blob) => {
    if (!sessionToken || !guestSession) return;
    
    setStep('processing');
    
    try {
      const formData = new FormData();
      formData.append('file', imageBlob, 'selfie.jpg');
      
      const result = await selfieMutation.mutateAsync({ slug, data: formData, token: sessionToken });

      if (!canProceedToGallery(result.status)) {
        toast.error(guestSelfieFailureCopy(result.status));
        setStep('selfie');
        return;
      }

      setGuestSession(guestSession, sessionToken, false);
      setStep('gallery');
      
      if (result.matched_photo_count > 0) {
        toast.success(`Found ${result.matched_photo_count} matching photos!`);
      } else {
        toast.info("No face matches found, but you can view the highlights!");
      }
    } catch (err) {
      toast.error('Failed to process selfie. Please try again.');
      setStep('selfie');
    }
  };

  const handleRetakeSelfie = () => {
    if (sessionToken && guestSession) {
      setGuestSession(guestSession, sessionToken, true);
    }
    setStep('selfie');
  };

  if (infoError) {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100">
        <EmptyState
          title="Gallery Unavailable"
          description="This gallery isn't available. Check the link from your photographer."
          icon={<AlertCircle className="h-8 w-8" />}
        />
      </div>
    );
  }

  if (infoLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 text-zinc-900 flex flex-col">
        <div className="w-full flex-1 p-4 max-w-md mx-auto space-y-8 mt-12 animate-pulse">
           <div className="h-12 w-12 bg-zinc-200/50 rounded-md mx-auto" />
           <div className="h-8 w-3/4 bg-zinc-200/50 rounded mx-auto" />
           <div className="h-4 w-1/2 bg-zinc-200/50 rounded mx-auto" />
           <div className="space-y-4 pt-8">
             <div className="h-12 bg-zinc-200/50 rounded" />
             <div className="h-12 bg-zinc-200/50 rounded" />
           </div>
        </div>
      </div>
    );
  }

  if (!infoData?.event) {
    return (
      <div className="flex h-screen items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100">
        <EmptyState title="Event Not Found" description="The event you are looking for does not exist." />
      </div>
    );
  }

  const { event, photographer } = infoData;

  if (event.status === 'archived') {
    return (
      <div className="flex h-[100dvh] items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100 p-4">
        <EmptyState
          title="Gallery Unavailable"
          description="This gallery is no longer available."
          icon={<Lock className="h-12 w-12 text-zinc-400" />}
        />
      </div>
    );
  }

  if (!isGalleryReady(event.status)) {
    return <GalleryNotReady eventName={event.name} />;
  }

  if (!event.guestLinkActive) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100 p-4">
        <EmptyState 
          title="Gallery Unavailable" 
          description="The guest link for this event is currently inactive." 
          icon={<Lock className="h-12 w-12 text-zinc-400" />} 
        />
      </div>
    );
  }
  
  const branding = (
    <div className="text-center w-full">
      {photographer.logo_url ? (
        <img src={photographer.logo_url} alt={photographer.studio_name} className="h-12 w-auto mx-auto mb-4" />
      ) : (
        <div className="h-12 w-12 rounded-md bg-zinc-900 text-white flex items-center justify-center mx-auto mb-4 font-bold text-xl uppercase">
          {getInitials(photographer.studio_name)}
        </div>
      )}
      <h1 className="text-2xl font-bold tracking-tight">{event.name}</h1>
      <p className="text-sm text-muted-foreground mt-2">Find your photos from the wedding!</p>
    </div>
  );

  return (
    <ErrorBoundary>
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100 text-zinc-900 flex flex-col items-center">
      {step === 'auth' && (
        <div className="w-full flex-1 flex flex-col items-center justify-center p-4">
          <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-2xl shadow-xl ring-1 ring-zinc-950/5">
            {branding}
            <div className="pt-4 border-t border-zinc-100">
              <p className="text-sm text-zinc-500 mb-6 text-center">
                Enter your details below to see the photos you appear in.
              </p>
              <OtpForm 
                onSendOtp={handleSendOtp} 
                onVerifyOtp={handleVerifyOtp} 
                isLoading={authMutation.isPending || verifyMutation.isPending} 
              />
            </div>
          </div>
        </div>
      )}

      {step === 'selfie' && (
        <div className="w-full flex-1 flex flex-col items-center justify-center p-4">
          <SelfieCapture 
            onCapture={handleSelfieCapture} 
            isLoading={selfieMutation.isPending} 
          />
        </div>
      )}

      {step === 'processing' && (
        <div className="w-full flex-1 flex flex-col items-center justify-center">
          <ProcessingScreen 
            photographerName={photographer.studio_name}
            photographerLogo={photographer.logo_url}
          />
        </div>
      )}

      {step === 'gallery' && (
        <div className="w-full flex-1 flex flex-col">
          {photosError || highlightsError ? (
            <div className="flex-1 flex items-center justify-center p-6">
              <EmptyState
                title="Failed to load photos"
                description={photosError?.message || highlightsError?.message || "An unknown error occurred."}
                icon={<AlertCircle className="h-8 w-8 text-destructive" />}
                action={<Button onClick={() => { refetchPhotos(); refetchHighlights(); }}>Try again</Button>}
              />
            </div>
          ) : photosLoading || highlightsLoading ? (
            <div className="flex-1 p-6">
              <GallerySkeleton count={12} className="opacity-50" />
            </div>
          ) : (
            <PersonalizedGallery 
              photos={photosData}
              highlightPhotos={highlightsData}
              guestName={guestSession?.name || 'Guest'} 
              onRetakeSelfie={handleRetakeSelfie}
              downloadEnabled={event.downloadEnabled}
              photographerLogo={photographer.logo_url}
              eventName={event.name}
              onLoadMorePhotos={() => photosQuery.fetchNextPage()}
              hasMorePhotos={!!photosQuery.hasNextPage}
              isLoadingMorePhotos={photosQuery.isFetchingNextPage}
              onLoadMoreHighlights={() => highlightsQuery.fetchNextPage()}
              hasMoreHighlights={!!highlightsQuery.hasNextPage}
              isLoadingMoreHighlights={highlightsQuery.isFetchingNextPage}
              photoTotal={getPaginatedTotal(photosQuery.data?.pages, photosData.length)}
              highlightTotal={getPaginatedTotal(highlightsQuery.data?.pages, highlightsData.length)}
            />
          )}
        </div>
      )}
    </div>
    </ErrorBoundary>
  );
}
