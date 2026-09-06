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
}

export function GalleryHeader({
  event,
  photographer,
  className,
}: GalleryHeaderProps) {
  return (
    <header className={cn('w-full border-b border-border/10 bg-background/80 backdrop-blur-md sticky top-0 z-10', className)}>
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        
        {/* Photographer Branding */}
        <div className="flex items-center space-x-3">
          {photographer.logoUrl ? (
            <div className="relative h-8 w-8 rounded-md overflow-hidden">
              <Image src={photographer.logoUrl} alt={photographer.studioName} fill className="object-contain" />
            </div>
          ) : (
            <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center text-primary-foreground font-bold text-sm">
              {photographer.studioName.charAt(0)}
            </div>
          )}
          <span className="font-semibold hidden sm:inline-block">
            {photographer.studioName}
          </span>
        </div>

        {/* Event Details */}
        <div className="flex flex-col items-center flex-1 px-4">
          <h1 className="text-base sm:text-lg font-bold truncate max-w-full">
            {event.name}
          </h1>
          <p className="text-xs text-muted-foreground">
            {event.dateStart ? format(new Date(event.dateStart), 'MMM d, yyyy') : 'No Date'}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center">
          <Button variant="ghost" size="icon" className="rounded-full">
            <Share2 className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </header>
  );
}
