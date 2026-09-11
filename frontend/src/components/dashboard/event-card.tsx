'use client';

import Link from 'next/link';
import Image from 'next/image';
import { Camera, Users, FolderOpen, Calendar, MoreVertical, Archive, ArchiveRestore, Trash2 } from 'lucide-react';
import { Event } from '@/types/event';
import { StatusBadge } from '@/components/shared/status-badge';
import { Button } from '@/components/ui/button';
import { useArchiveEvent, useRestoreEvent, useDeleteEvent } from '@/hooks/use-events';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface EventCardProps {
  event: Event;
}

export function EventCard({ event }: EventCardProps) {
  const archiveEventMutation = useArchiveEvent();
  const restoreEventMutation = useRestoreEvent();
  const deleteEventMutation = useDeleteEvent();

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

  const handleArchive = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm('Are you sure you want to archive this event? Archived events are only visible to you.')) {
      await archiveEventMutation.mutateAsync(event.id);
    }
  };

  const handleRestore = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm('Are you sure you want to unarchive this event? Guests will be able to view it again.')) {
      await restoreEventMutation.mutateAsync(event.id);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm('Are you sure you want to permanently delete this event? This action cannot be undone.')) {
      await deleteEventMutation.mutateAsync(event.id);
    }
  };

  return (
    <Link
      href={`/dashboard/events/${event.id}`}
      className="group block relative"
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
        <div className="flex-1 min-w-0 pr-8">
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
      </div>
      
      <div className="absolute top-1/2 -translate-y-1/2 right-4 flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
        <DropdownMenu>
          <DropdownMenuTrigger asChild onClick={(e) => e.preventDefault()}>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground bg-background/50 backdrop-blur-sm">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {event.status === 'archived' ? (
              <DropdownMenuItem onClick={handleRestore}>
                <ArchiveRestore className="mr-2 h-4 w-4" />
                Unarchive Event
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onClick={handleArchive}>
                <Archive className="mr-2 h-4 w-4" />
                Archive Event
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleDelete} className="text-destructive focus:text-destructive">
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Event
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </Link>
  );
}