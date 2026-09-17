'use client';

import { useEffect, useCallback } from 'react';
import { Photo } from '@/types/event';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { X, ChevronLeft, ChevronRight, Heart, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { DownloadButton } from './download-button';
import { buildPhotoSrcSet, toBrowserMediaSrc } from '@/lib/media-url';

interface PhotoViewerProps {
  photos: Photo[];
  currentIndex: number;
  isOpen: boolean;
  onClose: () => void;
  onChangeIndex: (index: number) => void;
  downloadEnabled?: boolean;
  favoritePhotoIds?: Set<string>;
  onToggleFavorite?: (photoId: string) => void;
  sharedPhotoIds?: Set<string>;
  onToggleShare?: (photoId: string) => void;
}

export function PhotoViewer({
  photos,
  currentIndex,
  isOpen,
  onClose,
  onChangeIndex,
  downloadEnabled = true,
  favoritePhotoIds,
  onToggleFavorite,
  sharedPhotoIds,
  onToggleShare
}: PhotoViewerProps) {
  const currentPhoto = photos[currentIndex];
  const isFavorite = currentPhoto ? favoritePhotoIds?.has(currentPhoto.id) : false;
  const isShared = currentPhoto ? sharedPhotoIds?.has(currentPhoto.id) : false;
  const prefersReducedMotion = useReducedMotion();
  const viewerSrc = currentPhoto?.previewUrl ?? currentPhoto?.proxyUrl ?? null;

  // Warm the browser cache for the photos either side so swiping and arrow
  // keys feel instant instead of showing a blank frame while S3 responds.
  useEffect(() => {
    if (!isOpen) return;

    for (const offset of [1, -1]) {
      const neighbour = photos[currentIndex + offset];
      const neighbourSrc = neighbour?.previewUrl ?? neighbour?.proxyUrl;
      if (!neighbourSrc) continue;
      const image = new window.Image();
      image.src = toBrowserMediaSrc(neighbourSrc);
    }
  }, [isOpen, currentIndex, photos]);

  const handlePrevious = useCallback(() => {
    if (currentIndex > 0) onChangeIndex(currentIndex - 1);
  }, [currentIndex, onChangeIndex]);

  const handleNext = useCallback(() => {
    if (currentIndex < photos.length - 1) onChangeIndex(currentIndex + 1);
  }, [currentIndex, photos.length, onChangeIndex]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') handlePrevious();
      if (e.key === 'ArrowRight') handleNext();
    };

    window.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'auto';
    };
  }, [isOpen, onClose, handlePrevious, handleNext]);

  return (
    <AnimatePresence>
      {isOpen && currentPhoto && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.2 } }}
        transition={{ duration: 0.2 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/95 backdrop-blur-sm"
      >
        {/* Toolbar */}
        <div className="absolute top-0 left-0 right-0 p-4 flex justify-between items-center z-10 bg-gradient-to-b from-black/60 to-transparent">
          <div className="text-white/80 text-sm font-medium">
            {currentIndex + 1} / {photos.length}
          </div>
          <div className="flex items-center gap-2">
            {onToggleFavorite && currentPhoto && (
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  "rounded-full transition-colors",
                  isFavorite 
                    ? "text-white bg-white/20 hover:bg-white/30 hover:text-white" 
                    : "text-white hover:bg-white/20 hover:text-white"
                )}
                onClick={() => onToggleFavorite(currentPhoto.id)}
                title={isFavorite ? "Remove from Favorites" : "Add to Favorites"}
              >
                <Heart className={cn("h-6 w-6", isFavorite && "fill-current")} />
              </Button>
            )}
            {onToggleShare && currentPhoto && (
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  "rounded-full transition-colors",
                  isShared 
                    ? "text-black bg-white hover:bg-white/90 hover:text-black" 
                    : "text-white hover:bg-white/20 hover:text-white"
                )}
                onClick={() => onToggleShare(currentPhoto.id)}
                title={isShared ? "Remove from Highlights (hide from all guests)" : "Add to Highlights (visible to all guests)"}
              >
                <Users className={cn("h-6 w-6", isShared && "fill-current")} />
              </Button>
            )}
            {downloadEnabled && (
              <DownloadButton
                photoId={currentPhoto.id}
                eventId={currentPhoto.eventId}
                originalFilename={currentPhoto.filename}
                variant="ghost"
                size="icon"
                iconClassName="h-6 w-6"
                className="text-white hover:bg-white/20 hover:text-white rounded-full"
              />
            )}
            <Button
              variant="ghost"
              size="icon"
              className="text-white hover:bg-white/20 hover:text-white rounded-full"
              onClick={onClose}
            >
              <X className="h-6 w-6" />
            </Button>
          </div>
        </div>

        {/* Navigation Arrows */}
        {currentIndex > 0 && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-4 top-1/2 -translate-y-1/2 text-white hover:bg-white/20 hover:text-white rounded-full h-12 w-12 z-10 hidden sm:flex"
            onClick={handlePrevious}
          >
            <ChevronLeft className="h-8 w-8" />
          </Button>
        )}
        
        {currentIndex < photos.length - 1 && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-4 top-1/2 -translate-y-1/2 text-white hover:bg-white/20 hover:text-white rounded-full h-12 w-12 z-10 hidden sm:flex"
            onClick={handleNext}
          >
            <ChevronRight className="h-8 w-8" />
          </Button>
        )}

        {/* Main Image */}
        <motion.div
          key={currentPhoto.id}
          layoutId={prefersReducedMotion ? undefined : `photo-container-${currentPhoto.id}`}
          initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.95, transition: { duration: 0.2 } }}
          transition={{ duration: prefersReducedMotion ? 0 : 0.2 }}
          className="relative w-full h-full p-4 sm:p-12 flex items-center justify-center"
          // Basic swipe handling
          drag="x"
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.2}
          onDragEnd={(e, { offset, velocity }) => {
            const swipe = Math.abs(offset.x) * velocity.x;
            if (swipe < -100) {
              handleNext();
            } else if (swipe > 100) {
              handlePrevious();
            }
          }}
        >
          {viewerSrc ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={toBrowserMediaSrc(viewerSrc)}
              srcSet={buildPhotoSrcSet(currentPhoto)}
              sizes="100vw"
              alt={currentPhoto.filename}
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-white/50">
              <span className="text-lg">Image Processing...</span>
              <span className="text-sm mt-2">Please check back later</span>
            </div>
          )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
