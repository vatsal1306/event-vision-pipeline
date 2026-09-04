'use client';

import Link from 'next/link';
import Image from 'next/image';
import { Camera, Users, FolderOpen, Calendar } from 'lucide-react';
import { Event } from '@/types/event';
import { StatusBadge } from '@/components/shared/status-badge';

interface EventCardProps {
  event: Event;
}

export function EventCard({ event }: EventCardProps) {

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'TBD';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const dateRange = event.dateEnd
    ? `${formatDate(event.dateStart)} – ${formatDate(event.dateEnd)}`
    : formatDate(event.dateStart);

  return (
    <Link
      href={`/dashboard/events/${event.id}`}
      className="group block"
    >
      <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-all hover:border-primary/50 hover:shadow-sm">
        <div className="relative flex h-20 w-20 shrink-0 overflow-hidden items-center justify-center rounded-lg bg-muted">
          {event.coverPhotoId ? (
            <Image 
              src={`https://images.unsplash.com/photo-1511285560929-80b456fea0bc?w=300&h=300&fit=crop`} 
              alt={event.name} 
              fill 
              className="object-cover"
            />
          ) : (
            <Camera className="h-10 w-10 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="font-semibold truncate">{event.name}</h3>
              <p className="text-sm text-muted-foreground">
                {dateRange} · {event.eventType.charAt(0).toUpperCase() + event.eventType.slice(1)} ·{' '}
                {event.totalPhotos.toLocaleString()} photos · {event.folderCount} folders
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Users className="h-4 w-4" />
                <span>{event.guestCount} guests viewed</span>
              </div>
              <StatusBadge 
                status={event.status} 
                progress={event.processedPhotos && event.totalPhotos > 0
                  ? Math.round((event.processedPhotos / event.totalPhotos) * 100)
                  : undefined}
              />
            </div>
          </div>
        </div>
        <FolderOpen className="h-5 w-5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </Link>
  );
}