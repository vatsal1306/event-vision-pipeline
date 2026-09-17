'use client';

import { Photo } from '@/types/event';
import { ResponsiveImage } from '@/components/shared/responsive-image';
import { buildPhotoSrcSet } from '@/lib/media-url';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { Heart, Users, Loader2 } from 'lucide-react';
import { DownloadButton } from './download-button';
import { useWindowVirtualizer } from '@tanstack/react-virtual';
import { useEffect, useState, useCallback } from 'react';
import { INFINITE_SCROLL_THRESHOLD_PX } from '@/lib/constants';
import { shouldFetchNextPage } from '@/lib/pagination';
import React from 'react';
import { Button } from '@/components/ui/button';

/**
 * Rendered tile width per breakpoint, mirroring the column counts chosen in
 * `updateCols` below. Lets the browser pick the smallest adequate rendition
 * from `srcSet` instead of always downloading the largest.
 */
const GRID_TILE_SIZES =
  '(max-width: 639px) 50vw, (max-width: 767px) 33vw, (max-width: 1023px) 25vw, 20vw';

interface GalleryGridProps {
  photos: Photo[];
  onPhotoClick: (index: number) => void;
  className?: string;
  downloadEnabled?: boolean;
  layoutMode?: 'guest' | 'couple' | 'dashboard';
  favoritePhotoIds?: Set<string>;
  onToggleFavorite?: (photoId: string) => void;
  sharedPhotoIds?: Set<string>;
  onToggleShare?: (photoId: string) => void;
  /** Called when the user scrolls near the bottom to load more pages. */
  onLoadMore?: () => void;
  /** Whether there are more pages to load. */
  hasMore?: boolean;
  /** Whether a next page is currently being fetched. */
  isLoadingMore?: boolean;
}

export function GalleryGrid({
  photos,
  onPhotoClick,
  className,
  downloadEnabled = true,
  layoutMode = 'dashboard',
  favoritePhotoIds,
  onToggleFavorite,
  sharedPhotoIds,
  onToggleShare,
  onLoadMore,
  hasMore = false,
  isLoadingMore = false,
}: GalleryGridProps) {
  const [columns, setColumns] = useState(3);
  const [containerWidth, setContainerWidth] = useState(0);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const sentinelRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateCols = () => {
      const w = window.innerWidth;
      
      if (w < 640) {
        setColumns(2);
      } else if (w < 768) {
        setColumns(3);
      } else if (w < 1024) {
        setColumns(layoutMode === 'guest' ? 3 : 4);
      } else if (w < 1280) {
        setColumns(layoutMode === 'guest' ? 4 : 5);
      } else {
        setColumns(layoutMode === 'guest' ? 4 : 6);
      }
      
      if (containerRef.current) {
        setContainerWidth(containerRef.current.getBoundingClientRect().width);
      }
    };
    updateCols();
    window.addEventListener('resize', updateCols);
    return () => window.removeEventListener('resize', updateCols);
  }, [layoutMode]);

  const onLoadMoreRef = React.useRef(onLoadMore);
  onLoadMoreRef.current = onLoadMore;

  const handleLoadMore = useCallback(() => {
    if (hasMore && !isLoadingMore && onLoadMoreRef.current) {
      onLoadMoreRef.current();
    }
  }, [hasMore, isLoadingMore]);

  useEffect(() => {
    if (!onLoadMore) return;

    const handleScroll = () => {
      const distanceFromBottomPx =
        document.documentElement.scrollHeight - (window.innerHeight + window.scrollY);
      if (
        shouldFetchNextPage({
          hasMore,
          isLoadingMore,
          distanceFromBottomPx,
          thresholdPx: INFINITE_SCROLL_THRESHOLD_PX,
        })
      ) {
        handleLoadMore();
      }
    };

    window.addEventListener('scroll', handleScroll);
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, [onLoadMore, handleLoadMore]);

  // Keep fetching when the current page is empty but more pages exist (e.g. client filters).
  useEffect(() => {
    if (photos.length === 0) {
      handleLoadMore();
    }
  }, [photos.length, handleLoadMore]);

  const rowVirtualizer = useWindowVirtualizer({
    count: Math.ceil(photos.length / columns),
    estimateSize: () => (containerWidth ? containerWidth / columns : 200),
    overscan: 5,
  });

  if (photos.length === 0) {
    if (hasMore || isLoadingMore) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      );
    }
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <p>No photos found.</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={cn('w-full px-4 pb-20', className)}>
      <div 
        className="relative w-full" 
        style={{ height: rowVirtualizer.getTotalSize() }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const startIndex = virtualRow.index * columns;
          const rowPhotos = photos.slice(startIndex, startIndex + columns);

          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              ref={rowVirtualizer.measureElement}
              className="absolute top-0 left-0 w-full flex gap-[2px]"
              style={{ transform: `translateY(${virtualRow.start}px)` }}
            >
              {rowPhotos.map((photo, colIndex) => {
                const index = startIndex + colIndex;
                const isFavorite = favoritePhotoIds?.has(photo.id);
                const isShared = sharedPhotoIds?.has(photo.id);

                return (
                  <div key={photo.id} style={{ width: `${100 / columns}%` }} className="pb-[2px]">
                    <motion.div
                      layoutId={`photo-container-${photo.id}`}
                      className="relative group cursor-pointer overflow-hidden bg-muted aspect-square rounded-[2px]"
                      onClick={() => onPhotoClick(index)}
                    >
                      {photo.thumbUrl ?? photo.proxyUrl ? (
                        <ResponsiveImage
                          src={(photo.thumbUrl ?? photo.proxyUrl) as string}
                          srcSet={buildPhotoSrcSet(photo)}
                          sizes={GRID_TILE_SIZES}
                          isPriority={virtualRow.index === 0}
                          alt={photo.filename}
                          blurhash={photo.blurhash}
                          aspectRatio={1}
                          className="w-full h-full object-cover rounded-[2px]"
                          imageClassName="group-hover:scale-105 transition-transform duration-500"
                        />
                      ) : (
                        <div className="w-full h-full bg-muted flex items-center justify-center text-muted-foreground">
                          <span className="text-xs">Processing...</span>
                        </div>
                      )}
                      
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors duration-300" />
                      
                      {onToggleFavorite && (
                        <div className={cn(
                          "absolute top-2 right-2 transition-opacity duration-300",
                          isFavorite ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                        )}>
                          <Button
                            variant="secondary"
                            size="icon"
                            className={cn(
                              "rounded-full shadow-sm hover:bg-background h-8 w-8",
                              isFavorite ? "bg-background text-red-500 hover:text-red-600" : "bg-background/80 backdrop-blur-md"
                            )}
                            onClick={(e) => {
                              e.stopPropagation();
                              onToggleFavorite(photo.id);
                            }}
                          >
                            <Heart className={cn("h-4 w-4", isFavorite && "fill-current")} />
                          </Button>
                        </div>
                      )}

                      {onToggleShare && (
                        <div className={cn(
                          "absolute top-2 left-2 transition-opacity duration-300",
                          isShared ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                        )}>
                          <Button
                            variant="secondary"
                            size="icon"
                            className={cn(
                              "rounded-full shadow-sm hover:bg-background h-8 w-8",
                              isShared ? "bg-background text-primary" : "bg-background/80 backdrop-blur-md"
                            )}
                            onClick={(e) => {
                              e.stopPropagation();
                              onToggleShare(photo.id);
                            }}
                          >
                            <Users className={cn("h-4 w-4", isShared && "fill-current")} />
                          </Button>
                        </div>
                      )}
                      
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
        })}
      </div>
      {/* Sentinel for infinite scroll */}
      {onLoadMore && (
        <div ref={sentinelRef} className="w-full flex justify-center py-6">
          {isLoadingMore && (
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          )}
        </div>
      )}
    </div>
  );
}
