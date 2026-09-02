'use client';

import { Photo } from '@/types/event';
import { ResponsiveImage } from '@/components/shared/responsive-image';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { DownloadButton } from './download-button';

interface GalleryGridProps {
  photos: Photo[];
  onPhotoClick: (index: number) => void;
  className?: string;
  downloadEnabled?: boolean;
}

export function GalleryGrid({
  photos,
  onPhotoClick,
  className,
  downloadEnabled = true,
}: GalleryGridProps) {
  if (photos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <p>No photos found.</p>
      </div>
    );
  }

  return (
    <div 
      className={cn(
        'columns-2 sm:columns-3 md:columns-4 lg:columns-5 xl:columns-6 gap-4 space-y-4 px-4 pb-20',
        className
      )}
    >
      {photos.map((photo, index) => {
        // Calculate aspect ratio for the image container to prevent layout shift
        const aspectRatio = photo.width && photo.height ? photo.width / photo.height : 1;

        return (
          <motion.div
            key={photo.id}
            layoutId={`photo-container-${photo.id}`}
            className="break-inside-avoid relative group cursor-pointer rounded-md overflow-hidden bg-muted"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: Math.min(index * 0.05, 0.5) }}
            onClick={() => onPhotoClick(index)}
          >
            <ResponsiveImage
              src={photo.proxyUrl || ''}
              alt={photo.filename}
              aspectRatio={aspectRatio}
              className="w-full h-auto rounded-md"
              imageClassName="group-hover:scale-105 transition-transform duration-500"
            />
            
            {/* Hover overlay */}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-300" />
            
            {downloadEnabled && (
              <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <DownloadButton
                  photoId={photo.id}
                  originalFilename={photo.filename}
                  variant="secondary"
                  size="icon"
                  className="rounded-full shadow-lg bg-background/80 hover:bg-background backdrop-blur-md h-8 w-8"
                />
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
