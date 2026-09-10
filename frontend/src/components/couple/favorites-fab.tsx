'use client';

import { Heart } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface FavoritesFabProps {
  count: number;
  isActive: boolean;
  onClick: () => void;
  className?: string;
}

export function FavoritesFab({ count, isActive, onClick, className }: FavoritesFabProps) {
  return (
    <div className={cn("fixed bottom-6 right-6 z-40 transition-transform duration-300 hover:scale-105", className)}>
      <Button
        size="lg"
        onClick={onClick}
        className={cn(
          "rounded-pill shadow-xl flex items-center gap-2 px-6 h-14 border border-white/10",
          isActive 
            ? "bg-white text-ink hover:bg-white/90" 
            : "bg-ink/80 text-white backdrop-blur-md hover:bg-ink"
        )}
      >
        <Heart className={cn("h-5 w-5", isActive || count > 0 ? "fill-current text-primary" : "")} />
        <span className="font-semibold text-sm">
          {isActive ? 'All Photos' : `Favorites (${count})`}
        </span>
      </Button>
    </div>
  );
}
