'use client';

import { Photo } from '@/types/event';
import { ResponsiveImage } from '@/components/shared/responsive-image';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { DownloadButton } from './download-button';
import { useWindowVirtualizer } from '@tanstack/react-virtual';
import { useEffect, useMemo, useState } from 'react';

interface GalleryGridProps {
  photos: Photo[];
  onPhotoClick: (index: number) => void;
  className?: string;
  downloadEnabled?: boolean;
}

function VirtualColumn({ 
  photos, 
  onPhotoClick,
  downloadEnabled
}: { 
  photos: { photo: Photo, originalIndex: number }[], 
  onPhotoClick: (idx: number) => void,
  downloadEnabled: boolean
}) {
  const virtualizer = useWindowVirtualizer({
    count: photos.length,
    estimateSize: (index) => {
      const p = photos[index].photo;
      const aspectRatio = p.width && p.height ? p.width / p.height : 1;
      return 300 / aspectRatio + 16;
    },
    overscan: 5,
  });

  return (
    <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
      {virtualizer.getVirtualItems().map((virtualItem) => {
        const { photo, originalIndex } = photos[virtualItem.index];
        const aspectRatio = photo.width && photo.height ? photo.width / photo.height : 1;

        return (
          <div
            key={virtualItem.key}
            data-index={virtualItem.index}
            ref={virtualizer.measureElement}
            className="absolute top-0 left-0 w-full pb-4"
            style={{ transform: `translateY(${virtualItem.start}px)` }}
          >
            <motion.div
              layoutId={`photo-container-${photo.id}`}
              className="relative group cursor-pointer rounded-md overflow-hidden bg-muted"
              onClick={() => onPhotoClick(originalIndex)}
            >
              <ResponsiveImage
                src={photo.proxyUrl || ''}
                alt={photo.filename}
                blurhash={photo.blurhash}
                aspectRatio={aspectRatio}
                className="w-full h-auto rounded-md"
                imageClassName="group-hover:scale-105 transition-transform duration-500"
              />
              
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-300" />
              
              {downloadEnabled && (
                <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <DownloadButton
                    photoId={photo.id}
                    eventId={photo.eventId}
                    originalFilename={photo.filename}
                    variant="secondary"
                    size="icon"
                    className="rounded-full shadow-lg bg-background/80 hover:bg-background backdrop-blur-md h-8 w-8"
                  />
                </div>
              )}
            </motion.div>
          </div>
        );
      })}
    </div>
  );
}

export function GalleryGrid({
  photos,
  onPhotoClick,
  className,
  downloadEnabled = true,
}: GalleryGridProps) {
  const [columns, setColumns] = useState(3);

  useEffect(() => {
    const updateCols = () => {
      const w = window.innerWidth;
      if (w < 640) setColumns(2);
      else if (w < 768) setColumns(3);
      else if (w < 1024) setColumns(4);
      else if (w < 1280) setColumns(5);
      else setColumns(6);
    };
    updateCols();
    window.addEventListener('resize', updateCols);
    return () => window.removeEventListener('resize', updateCols);
  }, []);

  const columnData = useMemo(() => {
    const cols = Array.from({ length: columns }, () => [] as { photo: Photo, originalIndex: number }[]);
    const colHeights = new Array(columns).fill(0);

    photos.forEach((photo, index) => {
      const shortestCol = colHeights.indexOf(Math.min(...colHeights));
      cols[shortestCol].push({ photo, originalIndex: index });
      const aspect = photo.width && photo.height ? photo.width / photo.height : 1;
      colHeights[shortestCol] += (1 / aspect);
    });

    return cols;
  }, [photos, columns]);

  if (photos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <p>No photos found.</p>
      </div>
    );
  }

  return (
    <div className={cn('flex gap-4 px-4 pb-20 w-full', className)}>
      {columnData.map((colPhotos, i) => (
        <VirtualColumn 
          key={i} 
          photos={colPhotos} 
          onPhotoClick={onPhotoClick} 
          downloadEnabled={downloadEnabled}
        />
      ))}
    </div>
  );
}
