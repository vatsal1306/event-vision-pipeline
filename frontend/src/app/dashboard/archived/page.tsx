'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Archive, Search, Filter, ChevronDown, AlertCircle } from 'lucide-react';
import { EventCard } from '@/components/dashboard/event-card';
import { useEvents } from '@/hooks/use-events';
import { EventListSkeleton } from '@/components/dashboard/event-list-skeleton';
import { ErrorBoundary } from '@/components/shared/error-boundary';
import { EmptyState } from '@/components/shared/empty-state';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
export default function ArchivedEventsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name'>('newest');

  const { data: events = [], isLoading, error, refetch } = useEvents();

  const filteredEvents = events
    .filter((event) => {
      if (event.status !== 'archived') return false;
      const matchesSearch = event.name.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesSearch;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        case 'oldest':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        case 'name':
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Archived Events ({filteredEvents.length})</h1>
            <p className="text-muted-foreground mt-1">View and manage your archived events</p>
          </div>
        </div>
        <EventListSkeleton count={3} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-16">
        <EmptyState
          title="Failed to load events"
          description={error.message}
          icon={<AlertCircle className="h-8 w-8 text-destructive" />}
          action={<Button onClick={() => refetch()}>Try again</Button>}
        />
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Archived Events ({filteredEvents.length})</h1>
            <p className="text-muted-foreground mt-1">View and manage your archived events</p>
          </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground z-10" />
          <Input
            type="text"
            placeholder="Search events..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 bg-lifted"
          />
        </div>
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-10">
                <Filter className="mr-2 h-4 w-4" />
                Sort
                <ChevronDown className="ml-2 h-4 w-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>Sort By</DropdownMenuLabel>
              <DropdownMenuRadioGroup value={sortBy} onValueChange={(val) => setSortBy(val as typeof sortBy)}>
                <DropdownMenuRadioItem value="newest">Most Recent</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="oldest">Oldest First</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="name">By Name</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {filteredEvents.length > 0 ? (
        <div className="space-y-4">
          {filteredEvents.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      ) : (
        <EmptyState
          title={searchQuery ? 'No events found' : 'No archived events'}
          description={searchQuery ? 'Try adjusting your search' : 'When you archive an event, it will appear here.'}
          icon={<Archive className="h-8 w-8 text-ink opacity-70" />}
          className="mt-8 py-16"
        />
      )}
    </div>
    </ErrorBoundary>
  );
}