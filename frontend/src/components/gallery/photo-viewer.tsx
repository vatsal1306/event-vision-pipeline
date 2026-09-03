'use client';

import { useEffect, useCallback } from 'react';
import { Photo } from '@/types/event';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DownloadButton } from './download-button';
import Image from 'next/image';

interface PhotoViewerProps {
  photos: Photo[];
  currentIndex: number;
  isOpen: boolean;
  onClose: () => void;
  onChangeIndex: (index: number) => void;
  downloadEnabled?: boolean;
}

export function PhotoViewer({
  photos,
  currentIndex,
  isOpen,
  onClose,
  onChangeIndex,
  downloadEnabled = true,
}: PhotoViewerProps) {
  const currentPhoto = photos[currentIndex];

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
            {downloadEnabled && (
              <DownloadButton
                photoId={currentPhoto.id}
                eventId={currentPhoto.eventId}
                originalFilename={currentPhoto.filename}
                variant="ghost"
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
          layoutId={`photo-container-${currentPhoto.id}`}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.2 } }}
          transition={{ duration: 0.2 }}
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
          <Image
            src={currentPhoto.proxyUrl || ''}
            alt={currentPhoto.filename}
            fill
            sizes="100vw"
            className="object-contain"
            priority
          />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
