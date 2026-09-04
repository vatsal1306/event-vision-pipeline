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
  if (count === 0 && !isActive) {
    return null; // Don't show unless there are favorites or we are currently in favorites view
  }

  return (
    <div className={cn("fixed bottom-6 right-6 z-40 transition-transform duration-300 hover:scale-105", className)}>
      <Button
        size="lg"
        onClick={onClick}
        className={cn(
          "rounded-full shadow-xl flex items-center gap-2 px-6 h-14 border border-border/50",
          isActive 
            ? "bg-primary text-primary-foreground hover:bg-primary/90" 
            : "bg-background/90 text-foreground backdrop-blur-md hover:bg-background"
        )}
      >
        <Heart className={cn("h-5 w-5", isActive || count > 0 ? "fill-current text-primary" : "")} />
        <span className="font-semibold text-sm">
          {isActive ? 'All Photos' : 'Favorites'} {count > 0 && `(${count})`}
        </span>
      </Button>
    </div>
  );
}
