'use client';

import { Event } from '@/types/event';
import { Photographer } from '@/types/user';
import { format } from 'date-fns';
import Image from 'next/image';
import { Logo } from '@/components/shared/logo';
import { cn } from '@/lib/utils';
import { Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface GalleryHeaderProps {
  event: Event;
  photographer: Photographer;
  className?: string;
  rightActions?: React.ReactNode;
  onShare?: () => void;
}

export function GalleryHeader({
  event,
  photographer,
  className,
  rightActions,
  onShare,
}: GalleryHeaderProps) {
  return (
    <header className={cn('w-full border-b border-border/10 bg-background/80 backdrop-blur-md sticky top-0 z-10', className)}>
      <div className="w-full max-w-screen-2xl mx-auto px-4 h-16 flex items-center justify-between">
        
        {/* Branding */}
        <div className="flex items-center space-x-4">
          <Logo size="sm" />
          <div className="flex items-center space-x-2 border-l border-border/20 pl-4 hidden md:flex">
          {photographer.logo_url ? (
            <div className="relative h-8 w-8 rounded-md overflow-hidden">
              <Image src={photographer.logo_url} alt={photographer.studio_name} fill className="object-contain" />
            </div>
          ) : (
            <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm">
              {photographer.studio_name.charAt(0)}
            </div>
          )}
          <span className="font-semibold text-sm hidden lg:inline-block">
            {photographer.studio_name}
          </span>
          </div>
        </div>

        {/* Event Details */}
        <div className="flex flex-col items-center flex-1 px-4">
          <h1 className="text-base sm:text-lg font-display font-bold truncate max-w-full">
            {event.name}
          </h1>
          <p className="text-xs text-muted-foreground">
            {event.dateStart ? format(new Date(event.dateStart), 'MMM d, yyyy') : 'No Date'}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {onShare && (
            <Button variant="ghost" size="icon" className="rounded-full hover:bg-accent hover:text-accent-foreground" onClick={onShare}>
              <Share2 className="h-5 w-5" />
            </Button>
          )}
          {rightActions}
        </div>
      </div>
    </header>
  );
}
