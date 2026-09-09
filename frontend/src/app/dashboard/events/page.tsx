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
import { AlertCircle } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export default function EventsPage() {
  const { photographer } = useAuthStore();
  const router = useRouter();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name' | 'status'>('newest');
  const [filterStatus, setFilterStatus] = useState<'all' | 'draft' | 'uploading' | 'processing' | 'ready' | 'archived'>('all');

  const { data: events = [], isLoading, error, refetch } = useEvents();
  const createEventMutation = useCreateEvent();

  const filteredEvents = events
    .filter((event) => {
      const matchesSearch = event.name.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = filterStatus === 'all' || event.status === filterStatus;
      return matchesSearch && matchesStatus;
    })
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
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-10">
                <Filter className="mr-2 h-4 w-4" />
                Filter & Sort
                <ChevronDown className="ml-2 h-4 w-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>Sort By</DropdownMenuLabel>
              <DropdownMenuRadioGroup value={sortBy} onValueChange={(val) => setSortBy(val as typeof sortBy)}>
                <DropdownMenuRadioItem value="newest">Most Recent</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="oldest">Oldest First</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="name">By Name</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="status">By Status</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
              <DropdownMenuSeparator />
              <DropdownMenuLabel>Filter by Status</DropdownMenuLabel>
              <DropdownMenuRadioGroup value={filterStatus} onValueChange={(val) => setFilterStatus(val as typeof filterStatus)}>
                <DropdownMenuRadioItem value="all">All Statuses</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="draft">Draft</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="uploading">Uploading</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="processing">Processing</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="ready">Ready</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="archived">Archived</DropdownMenuRadioItem>
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
    </ErrorBoundary>
  );
}