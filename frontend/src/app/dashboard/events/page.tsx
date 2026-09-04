'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Camera, Plus, Search, Filter, ChevronDown } from 'lucide-react';
import { EventCard } from '@/components/dashboard/event-card';
import { EventForm } from '@/components/dashboard/event-form';
import { useEvents, useCreateEvent, CreateEventData } from '@/hooks/use-events';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { EventListSkeleton } from '@/components/dashboard/event-list-skeleton';
import { ErrorBoundary } from '@/components/shared/error-boundary';
import { EmptyState } from '@/components/shared/empty-state';

const Throw = ({ error }: { error: Error }) => { throw error; };

export default function EventsPage() {
  const { photographer } = useAuthStore();
  const router = useRouter();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name' | 'status'>('newest');

  const { data: events = [], isLoading, error } = useEvents();
  const createEventMutation = useCreateEvent();

  const filteredEvents = events
    .filter((event) =>
      event.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
        case 'oldest':
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
        case 'name':
          return a.name.localeCompare(b.name);
        case 'status':
          const statusOrder = { draft: 0, uploading: 1, processing: 2, ready: 3, archived: 4 };
          return (statusOrder[a.status] || 5) - (statusOrder[b.status] || 5);
        default:
          return 0;
      }
    });

  const handleCreateEvent = async (data: CreateEventData) => {
    try {
      const created = await createEventMutation.mutateAsync(data);
      setIsCreateDialogOpen(false);
      router.push(`/dashboard/events/${created.id}`);
    } catch (err) {
      toast.error('Failed to create event. Please try again.');
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Your Events</h1>
            <p className="text-muted-foreground mt-1">Manage and organize your photography events</p>
          </div>
        </div>
        <EventListSkeleton count={3} />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorBoundary>
        <Throw error={error} />
      </ErrorBoundary>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Your Events</h1>
          <p className="text-muted-foreground mt-1">Manage and organize your photography events</p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Event
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search events..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-border rounded-lg bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Filter className="mr-2 h-4 w-4" />
            Filters
          </Button>
          <div className="relative">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="flex h-10 appearance-none items-center px-3 pr-8 text-sm border border-border rounded-lg bg-background"
            >
              <option value="newest">Most Recent</option>
              <option value="oldest">Oldest First</option>
              <option value="name">By Name</option>
              <option value="status">By Status</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          </div>
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
          title={searchQuery ? 'No events found' : 'No events yet'}
          description={searchQuery ? 'Try adjusting your search or filters' : 'Create your first event to get started'}
          icon={<Camera className="h-8 w-8 text-ink opacity-70" />}
          action={
            <Button onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Event
            </Button>
          }
          className="mt-8 py-16"
        />
      )}

      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create New Event</DialogTitle>
            <DialogDescription>Fill in the details to create a new photography event</DialogDescription>
          </DialogHeader>
          <EventForm
            onSubmit={handleCreateEvent}
            onCancel={() => setIsCreateDialogOpen(false)}
            isLoading={createEventMutation.isPending}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}