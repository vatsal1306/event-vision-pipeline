'use client';

import { useState, useEffect } from 'react';
import { useEventInfo } from '@/hooks/use-master-gallery';
import { useGuestAuth, useGuestVerify, useSubmitSelfie, useGuestPhotos } from '@/hooks/use-guest-gallery';
import { useGuestAuthStore } from '@/stores/guest-auth-store';
import { LoadingSpinner } from '@/components/shared/loading-spinner';
import { EmptyState } from '@/components/shared/empty-state';
import { Lock } from 'lucide-react';
import { OtpForm } from '@/components/guest/otp-form';
import { SelfieCapture } from '@/components/guest/selfie-capture';
import { ProcessingScreen } from '@/components/guest/processing-screen';
import { PersonalizedGallery } from '@/components/guest/personalized-gallery';
import { toast } from 'sonner';

type FlowStep = 'auth' | 'selfie' | 'processing' | 'gallery';

export default function GuestGalleryPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  
  // Queries
  const { data: infoData, isLoading: infoLoading, error: infoError } = useEventInfo(slug);
  
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
  const { data: photosData, isLoading: photosLoading } = useGuestPhotos(slug, !needsSelfie && isVerified ? sessionToken : null);

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
      const { accessToken } = await verifyMutation.mutateAsync({ slug, otp });
      // Initially, they need a selfie
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
        accessToken,
        true
      );
      toast.success('Successfully logged in');
    } catch (err) {
      toast.error('Invalid OTP. Use 123456 for testing.');
    }
  };

  const handleSelfieCapture = async (imageBlob: Blob) => {
    if (!sessionToken || !guestSession) return;
    
    setStep('processing');
    
    try {
      const formData = new FormData();
      formData.append('file', imageBlob, 'selfie.jpg');
      
      const { matchCount } = await selfieMutation.mutateAsync({ slug, data: formData });
      
      // Update session to indicate selfie is no longer needed
      setGuestSession(guestSession, sessionToken, false);
      
      // We will automatically transition to 'gallery' due to the useEffect watching needsSelfie,
      // but let's do it explicitly to be sure.
      setStep('gallery');
      
      if (matchCount > 0) {
        toast.success(`Found ${matchCount} matching photos!`);
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

  if (infoLoading) {
    return <div className="flex h-screen items-center justify-center bg-black"><LoadingSpinner /></div>;
  }

  if (infoError || !infoData) {
    return (
      <div className="flex h-screen items-center justify-center bg-black">
        <EmptyState title="Event Not Found" description="The event you are looking for does not exist." />
      </div>
    );
  }

  const { event, photographer } = infoData;

  if (!event.guestLinkActive) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black p-4">
        <EmptyState 
          title="Gallery Unavailable" 
          description="The guest link for this event is currently inactive." 
          icon={<Lock className="h-12 w-12 text-zinc-600" />} 
        />
      </div>
    );
  }
  
  const branding = (
    <div className="text-center w-full">
      {photographer.logoUrl ? (
        <img src={photographer.logoUrl} alt={photographer.studioName} className="h-12 w-auto mx-auto mb-4" />
      ) : (
        <div className="h-12 w-12 rounded-md bg-primary flex items-center justify-center mx-auto mb-4 font-bold text-xl">
          {photographer.studioName.charAt(0)}
        </div>
      )}
      <h1 className="text-2xl font-bold tracking-tight">{event.name}</h1>
      <p className="text-sm text-muted-foreground mt-2">Find your photos from the wedding!</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-black text-white flex flex-col items-center">
      {step === 'auth' && (
        <div className="w-full flex-1 flex flex-col items-center justify-center p-4">
          <div className="w-full max-w-md space-y-8 bg-zinc-900 p-8 rounded-xl border border-white/10">
            {branding}
            <div className="pt-4 border-t border-white/10">
              <p className="text-sm text-zinc-400 mb-6 text-center">
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
            photographerName={photographer.studioName}
            photographerLogo={photographer.logoUrl}
          />
        </div>
      )}

      {step === 'gallery' && (
        <div className="w-full flex-1 flex flex-col">
          {photosLoading ? (
            <div className="flex-1 flex items-center justify-center"><LoadingSpinner /></div>
          ) : (
            <PersonalizedGallery 
              photos={photosData?.items || []} 
              guestName={guestSession?.name || 'Guest'} 
              onRetakeSelfie={handleRetakeSelfie}
              downloadEnabled={event.downloadEnabled}
              photographerLogo={photographer.logoUrl}
              eventName={event.name}
            />
          )}
        </div>
      )}
    </div>
  );
}
