import { useState } from 'react';
import dynamic from 'next/dynamic';
import { LayoutGroup } from 'framer-motion';
import { Photo } from '@/types/event';
import { GalleryGrid } from '@/components/gallery/gallery-grid';
import { Button } from '@/components/ui/button';
import { Camera, Image as ImageIcon, Sparkles } from 'lucide-react';
import { EmptyState } from '@/components/shared/empty-state';
import { Logo } from '@/components/shared/logo';
import { cn } from '@/lib/utils';

const PhotoViewer = dynamic(
  () => import('@/components/gallery/photo-viewer').then(mod => mod.PhotoViewer),
  { ssr: false }
);

interface PersonalizedGalleryProps {
  photos: Photo[];
  highlightPhotos?: Photo[];
  guestName: string;
  onRetakeSelfie: () => void;
  downloadEnabled?: boolean;
  photographerLogo?: string | null;
  eventName?: string;
  /** Infinite scroll for My Photos tab. */
  onLoadMorePhotos?: () => void;
  hasMorePhotos?: boolean;
  isLoadingMorePhotos?: boolean;
  /** Infinite scroll for Highlights tab. */
  onLoadMoreHighlights?: () => void;
  hasMoreHighlights?: boolean;
  isLoadingMoreHighlights?: boolean;
}

export function PersonalizedGallery({ 
  photos, 
  highlightPhotos = [],
  guestName, 
  onRetakeSelfie, 
  downloadEnabled = true,
  photographerLogo,
  eventName,
  onLoadMorePhotos,
  hasMorePhotos = false,
  isLoadingMorePhotos = false,
  onLoadMoreHighlights,
  hasMoreHighlights = false,
  isLoadingMoreHighlights = false,
}: PersonalizedGalleryProps) {
  const [activeTab, setActiveTab] = useState<'my-photos' | 'highlights'>('my-photos');
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  const activePhotos = activeTab === 'my-photos' ? photos : highlightPhotos;

  const handlePhotoClick = (index: number) => {
    setViewerIndex(index);
    setViewerOpen(true);
  };

  // Render empty state only if we have NO photos in either tab and we are on 'my-photos'
  if (photos.length === 0 && highlightPhotos.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <EmptyState 
          title="No photos yet" 
          description="We couldn't find photos matching your face, and no highlights have been shared yet."
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
    <div className="flex flex-col w-full h-full max-w-7xl mx-auto pb-24">
      <div className="px-6 py-8 md:py-12 border-b border-zinc-200">
        <div className="flex items-center gap-4 mb-6">
          <Logo size="sm" />
          <div className="flex items-center gap-4 border-l border-zinc-200 pl-4">
            {photographerLogo && (
              <img src={photographerLogo} alt="Logo" className="h-8 w-auto opacity-80" />
            )}
            {eventName && (
              <span className="text-zinc-500 font-medium text-sm tracking-wide uppercase hidden sm:inline-block">{eventName}</span>
            )}
          </div>
        </div>
        <h2 className="text-2xl md:text-3xl font-bold text-zinc-900 tracking-tight">
          Hi {guestName}!
        </h2>
        <p className="text-zinc-500 mt-2 text-lg">
          {activeTab === 'my-photos' 
            ? `We found ${photos.length} photo${photos.length === 1 ? '' : 's'} of you.` 
            : 'Highlights shared by the couple for everyone.'}
        </p>
      </div>

      <div className="px-6 pb-6 pt-2">
        <div className="inline-flex h-10 items-center justify-center rounded-md bg-zinc-100 p-1 text-zinc-500 w-full max-w-md mx-auto sm:mx-0">
          <button
            onClick={() => setActiveTab('my-photos')}
            className={cn(
              "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 flex-1",
              activeTab === 'my-photos' ? "bg-white text-zinc-950 shadow-sm" : "hover:text-zinc-900"
            )}
          >
            <ImageIcon className="w-4 h-4 mr-2" />
            My Photos ({photos.length})
          </button>
          <button
            onClick={() => setActiveTab('highlights')}
            className={cn(
              "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 flex-1",
              activeTab === 'highlights' ? "bg-white text-zinc-950 shadow-sm" : "hover:text-zinc-900"
            )}
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Highlights ({highlightPhotos.length})
          </button>
        </div>
      </div>

      <LayoutGroup>
        {activePhotos.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
             <EmptyState 
                title={activeTab === 'my-photos' ? "No matches found" : "No highlights yet"} 
                description={
                  activeTab === 'my-photos' 
                    ? "We couldn't find photos matching your face." 
                    : "The couple hasn't shared any highlights yet."
                }
              />
          </div>
        ) : (
          <GalleryGrid
            key={activeTab}
            photos={activePhotos}
            onPhotoClick={handlePhotoClick}
            downloadEnabled={downloadEnabled}
            layoutMode="guest"
            className="flex-1"
            onLoadMore={activeTab === 'my-photos' ? onLoadMorePhotos : onLoadMoreHighlights}
            hasMore={activeTab === 'my-photos' ? hasMorePhotos : hasMoreHighlights}
            isLoadingMore={activeTab === 'my-photos' ? isLoadingMorePhotos : isLoadingMoreHighlights}
          />
        )}
      </LayoutGroup>

      <PhotoViewer
        photos={activePhotos}
        currentIndex={viewerIndex}
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        onChangeIndex={setViewerIndex}
        downloadEnabled={downloadEnabled}
      />

      <div className="fixed bottom-6 right-6 z-40 transition-transform duration-300 hover:scale-105">
        <Button
          size="lg"
          onClick={onRetakeSelfie}
          className="rounded-pill shadow-xl flex items-center gap-2 px-6 h-14 bg-white text-zinc-900 border border-zinc-200 hover:bg-zinc-50 backdrop-blur-md"
        >
          <Camera className="h-5 w-5" />
          <span className="font-semibold text-sm">Retake Selfie</span>
        </Button>
      </div>
    </div>
  );
}
