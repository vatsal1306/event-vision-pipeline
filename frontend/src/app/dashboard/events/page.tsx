'use client';

import Link from 'next/link';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Camera, Plus, Search, Filter, Calendar, Users, FolderOpen } from 'lucide-react';

export default function EventsPage() {
  const { photographer, logout } = useAuthStore();

  const mockEvents = [
    {
      id: '1',
      name: 'Rahul & Priya Wedding',
      date: '12 Jun 2026',
      type: 'Wedding',
      photos: 3450,
      folders: 12,
      guestsViewed: 186,
      status: 'ready' as const,
      coverImage: null,
    },
    {
      id: '2',
      name: 'Amit Corporate Summit',
      date: '28 May 2026',
      type: 'Corporate',
      photos: 890,
      folders: 3,
      guestsViewed: 0,
      status: 'processing' as const,
      progress: 67,
      coverImage: null,
    },
    {
      id: '3',
      name: 'Sneha Birthday Party',
      date: '15 May 2026',
      type: 'Birthday',
      photos: 240,
      folders: 1,
      guestsViewed: 34,
      status: 'archived' as const,
      coverImage: null,
    },
  ];

  const getStatusBadge = (status: string, progress?: number) => {
    const variants = {
      ready: 'bg-green-100 text-green-800 border-green-200',
      processing: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      uploading: 'bg-blue-100 text-blue-800 border-blue-200',
      draft: 'bg-gray-100 text-gray-800 border-gray-200',
      archived: 'bg-gray-100 text-gray-600 border-gray-200',
    };
    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${variants[status as keyof typeof variants] || variants.draft}`}>
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your Events</h1>
          <p className="text-muted-foreground mt-1">
            Manage and organize your photography events
          </p>
        </div>
        <Button asChild>
          <a href="/dashboard/events/new">
            <Plus className="mr-2 h-4 w-4" />
            Create Event
          </a>
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search events..."
            className="w-full pl-10 pr-4 py-2 border border-border rounded-lg bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Filter className="mr-2 h-4 w-4" />
            Filters
          </Button>
          <select className="flex h-10 items-center px-3 text-sm border border-border rounded-lg bg-background">
            <option>Most Recent</option>
            <option>Oldest First</option>
            <option>By Name</option>
            <option>By Status</option>
          </select>
        </div>
      </div>

      <div className="space-y-4">
        {mockEvents.map((event) => (
          <Link key={event.id} href={`/dashboard/events/${event.id}`} className="block">
            <div className="group flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-all hover:border-primary/50 hover:shadow-sm">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-lg bg-muted">
                <Camera className="h-10 w-10 text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold truncate">{event.name}</h3>
                    <p className="text-sm text-muted-foreground">
                      {event.date} · {event.type} · {event.photos.toLocaleString()} photos · {event.folders} folders
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Users className="h-4 w-4" />
                      <span>{event.guestsViewed} guests</span>
                    </div>
                    {getStatusBadge(event.status, event.progress)}
                  </div>
                </div>
              </div>
              <FolderOpen className="h-5 w-5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </Link>
        ))}
      </div>

      {mockEvents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Camera className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium">No events yet</h3>
          <p className="text-muted-foreground mt-1 mb-4">Create your first event to get started</p>
          <Button asChild>
            <a href="/dashboard/events/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Event
            </a>
          </Button>
        </div>
      )}
    </div>
  );
}