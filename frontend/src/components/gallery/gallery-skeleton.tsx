import { cn } from "@/lib/utils";

interface GallerySkeletonProps {
  count?: number;
  className?: string;
}

export function GallerySkeleton({ count = 12, className }: GallerySkeletonProps) {
  return (
    <div className={cn("grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div 
          key={i} 
          className="w-full bg-muted animate-pulse rounded-lg"
          style={{
            // Randomize aspect ratio slightly for masonry effect if used in a grid,
            // or just provide a square/rectangle base height
            aspectRatio: i % 3 === 0 ? '3/4' : i % 2 === 0 ? '4/3' : '1/1'
          }}
        />
      ))}
    </div>
  );
}
