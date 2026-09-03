'use client';

import Link from 'next/link';
import { Camera, Users, FolderOpen, Calendar } from 'lucide-react';
import { Event } from '@/types/event';

interface EventCardProps {
  event: Event;
}

export function EventCard({ event }: EventCardProps) {
  const getStatusBadge = (status: Event['status'], progress?: number) => {
    const variants = {
      ready: 'bg-green-100 text-green-800 border-green-200',
      processing: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      uploading: 'bg-blue-100 text-blue-800 border-blue-200',
      draft: 'bg-gray-100 text-gray-800 border-gray-200',
      archived: 'bg-gray-100 text-gray-600 border-gray-200',
    };
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
          variants[status] || variants.draft
        }`}
      >
        {status === 'processing' && progress ? (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
            Processing {progress}%
          </>
        ) : (
          status.charAt(0).toUpperCase() + status.slice(1)
        )}
      </span>
    );
  };

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
        <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg bg-muted">
          <Camera className="h-10 w-10 text-muted-foreground" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="font-semibold truncate">{event.name}</h3>
              <p className="text-sm text-muted-foreground">
                {dateRange} · {event.eventType.charAt(0).toUpperCase() + event.eventType.slice(1)} ·{' '}
                {event.totalPhotos.toLocaleString()} photos · {event.totalFaces > 0 ? event.totalFaces : '—'} faces
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Users className="h-4 w-4" />
                <span>{event.totalFaces > 0 ? Math.round(event.totalFaces / 2.5) : 0} guests</span>
              </div>
              {getStatusBadge(event.status, event.processedPhotos && event.totalPhotos > 0
                ? Math.round((event.processedPhotos / event.totalPhotos) * 100)
                : undefined)}
            </div>
          </div>
        </div>
        <FolderOpen className="h-5 w-5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </Link>
  );
}