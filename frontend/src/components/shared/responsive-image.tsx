'use client';

import { useState } from 'react';
import Image, { ImageProps } from 'next/image';
import { cn } from '@/lib/utils';

interface ResponsiveImageProps extends Omit<ImageProps, 'src'> {
  src: string;
  alt: string;
  aspectRatio?: number;
  className?: string;
  imageClassName?: string;
}

export function ResponsiveImage({
  src,
  alt,
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
      
      {isLoading && (
        <div className="absolute inset-0 bg-muted animate-pulse">
          <div className="w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-[shimmer_1.5s_infinite]" />
        </div>
      )}
    </div>
  );
}
