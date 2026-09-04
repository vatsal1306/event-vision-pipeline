import { useState } from 'react';
import dynamic from 'next/dynamic';
import { LayoutGroup } from 'framer-motion';
import { Photo } from '@/types/event';
import { GalleryGrid } from '@/components/gallery/gallery-grid';
import { Button } from '@/components/ui/button';
import { Camera } from 'lucide-react';
import { EmptyState } from '@/components/shared/empty-state';

const PhotoViewer = dynamic(
  () => import('@/components/gallery/photo-viewer').then(mod => mod.PhotoViewer),
  { ssr: false }
);

interface PersonalizedGalleryProps {
  photos: Photo[];
  guestName: string;
  onRetakeSelfie: () => void;
  downloadEnabled?: boolean;
}

export function PersonalizedGallery({ photos, guestName, onRetakeSelfie, downloadEnabled = true }: PersonalizedGalleryProps) {
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  const handlePhotoClick = (index: number) => {
    setViewerIndex(index);
    setViewerOpen(true);
  };

  if (photos.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <EmptyState 
          title="No matches found" 
          description="We couldn't find photos matching your face. This can happen if the lighting was different or if you appear in group photos from a distance. Please try again with a clearer selfie."
          icon={<Camera className="w-12 h-12 text-zinc-500" />}
          action={
            <Button onClick={onRetakeSelfie} size="lg" className="mt-4 rounded-full px-8">
              Retake Selfie
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full h-full max-w-7xl mx-auto">
      <div className="px-6 py-8 md:py-12">
        <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
          Hi {guestName}!
        </h2>
        <p className="text-zinc-400 mt-2 text-lg">
          We found {photos.length} photo{photos.length === 1 ? '' : 's'} of you.
        </p>
      </div>

      <LayoutGroup>
        <GalleryGrid
          photos={photos}
          onPhotoClick={handlePhotoClick}
          downloadEnabled={downloadEnabled}
          layoutMode="guest"
          className="flex-1"
        />
      </LayoutGroup>

      <PhotoViewer
        photos={photos}
        currentIndex={viewerIndex}
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        onChangeIndex={setViewerIndex}
        downloadEnabled={downloadEnabled}
      />
    </div>
  );
}
