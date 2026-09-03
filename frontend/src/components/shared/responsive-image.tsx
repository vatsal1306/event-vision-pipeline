'use client';

import { useState } from 'react';
import Image, { ImageProps } from 'next/image';
import { Blurhash } from 'react-blurhash';
import { cn } from '@/lib/utils';

interface ResponsiveImageProps extends Omit<ImageProps, 'src'> {
  src: string;
  alt: string;
  blurhash?: string | null;
  aspectRatio?: number;
  className?: string;
  imageClassName?: string;
}

export function ResponsiveImage({
  src,
  alt,
  blurhash,
  aspectRatio,
  className,
  imageClassName,
  ...props
}: ResponsiveImageProps) {
  const [isLoading, setIsLoading] = useState(true);

  return (
    <div
      className={cn(
        'relative overflow-hidden bg-muted',
        className
      )}
      style={aspectRatio ? { paddingBottom: `${(1 / aspectRatio) * 100}%` } : undefined}
    >
      <Image
        src={src}
        alt={alt}
        fill
        className={cn(
          'object-cover transition-opacity duration-300 ease-in-out',
          isLoading ? 'opacity-0' : 'opacity-100',
          imageClassName
        )}
        onLoad={() => setIsLoading(false)}
        {...props}
      />
      
      {isLoading && blurhash && (
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
      {isLoading && !blurhash && (
        <div className="absolute inset-0 bg-muted animate-pulse z-0">
          <div className="w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-[shimmer_1.5s_infinite]" />
        </div>
      )}
    </div>
  );
}
