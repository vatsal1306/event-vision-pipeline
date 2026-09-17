'use client';

import { useState } from 'react';
import { Blurhash } from 'react-blurhash';
import { toBrowserMediaSrc } from '@/lib/media-url';
import { cn } from '@/lib/utils';

interface ResponsiveImageProps {
  src: string;
  alt: string;
  blurhash?: string | null;
  aspectRatio?: number;
  className?: string;
  imageClassName?: string;
  /** Candidate renditions with `w` descriptors, from `buildPhotoSrcSet`. */
  srcSet?: string;
  /** Rendered tile width per breakpoint, required for `srcSet` to be useful. */
  sizes?: string;
  /** Skip lazy loading for tiles likely to be above the fold. */
  isPriority?: boolean;
}

/**
 * Event photo preview. Uses a plain img so presigned S3 URLs and signed
 * `/api/.../preview` paths are requested directly by the browser instead of
 * being re-proxied through `/_next/image`.
 */
export function ResponsiveImage({
  src,
  alt,
  blurhash,
  aspectRatio,
  className,
  imageClassName,
  srcSet,
  sizes,
  isPriority = false,
}: ResponsiveImageProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const resolvedSrc = toBrowserMediaSrc(src);

  return (
    <div
      className={cn('relative overflow-hidden bg-muted', className)}
      style={aspectRatio ? { paddingBottom: `${(1 / aspectRatio) * 100}%` } : undefined}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={resolvedSrc}
        srcSet={srcSet}
        sizes={sizes}
        loading={isPriority ? 'eager' : 'lazy'}
        decoding="async"
        fetchPriority={isPriority ? 'high' : 'auto'}
        alt={alt}
        className={cn(
          'absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ease-in-out',
          isLoading && !hasError ? 'opacity-0' : 'opacity-100',
          imageClassName
        )}
        onLoad={() => setIsLoading(false)}
        onError={() => {
          setIsLoading(false);
          setHasError(true);
        }}
      />

      {isLoading && blurhash && !hasError && (
        <div className="absolute inset-0 z-0">
          <Blurhash
            hash={blurhash}
            width="100%"
            height="100%"
            resolutionX={32}
            resolutionY={32}
            punch={1}
          />
        </div>
      )}

      {hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted text-muted-foreground z-10 flex-col gap-2">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
          <span className="text-xs">Failed to load</span>
        </div>
      )}

      {isLoading && !blurhash && !hasError && (
        <div className="absolute inset-0 bg-muted animate-pulse z-0">
          <div className="w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-[shimmer_1.5s_infinite]" />
        </div>
      )}
    </div>
  );
}
