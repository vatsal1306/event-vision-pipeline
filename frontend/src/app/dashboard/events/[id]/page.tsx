'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams, useParams } from 'next/navigation';
import { useEvent, useUpdateEvent, useArchiveEvent, useRestoreEvent, useDeleteEvent } from '@/hooks/use-events';
import { useFolders } from '@/hooks/use-folders';
import { Photo } from '@/types/event';
import { StatusBadge } from '@/components/shared/status-badge';
import { FolderTree } from '@/components/dashboard/folder-tree';
import { PhotoDetailViewer } from '@/components/dashboard/photo-detail-viewer';
import { AnalyticsOverview } from '@/components/dashboard/analytics-overview';
import { LeadTable } from '@/components/dashboard/lead-table';
import { LinkGenerator } from '@/components/dashboard/link-generator';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Settings, Image as ImageIcon, UploadCloud, BarChart3, Share2, MoreHorizontal, Archive, ArchiveRestore, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const PhotoGrid = dynamic(() => import('@/components/dashboard/photo-grid').then(m => m.PhotoGrid), { ssr: false });
const UploadDropzone = dynamic(() => import('@/components/dashboard/upload-dropzone').then(m => m.UploadDropzone), { ssr: false });
const UploadProgress = dynamic(() => import('@/components/dashboard/upload-progress').then(m => m.UploadProgress), { ssr: false });

import { ErrorBoundary } from '@/components/shared/error-boundary';
import { EmptyState } from '@/components/shared/empty-state';
import { AlertCircle } from 'lucide-react';
import { EventForm, type EventFormData } from '@/components/dashboard/event-form';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export default function EventDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const id = params.id as string;
  const currentTab = searchParams.get('tab') || 'photos';
  const folderId = searchParams.get('folderId');

  const { data: event, isLoading: isEventLoading, error: eventError, refetch } = useEvent(id);
  const { data: folders = [], isLoading: isFoldersLoading } = useFolders(id);
  const updateEventMutation = useUpdateEvent();
  const archiveEventMutation = useArchiveEvent();
  const restoreEventMutation = useRestoreEvent();
  const deleteEventMutation = useDeleteEvent();
  
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const handleUpdateEvent = async (data: EventFormData) => {
    await updateEventMutation.mutateAsync({ id, data });
    setIsSettingsOpen(false);
  };

  const handleArchive = async () => {
    if (window.confirm('Are you sure you want to archive this event? Archived events are only visible to you.')) {
      await archiveEventMutation.mutateAsync(id);
    }
  };

  const handleRestore = async () => {
    if (window.confirm('Are you sure you want to unarchive this event? Guests will be able to view it again.')) {
      await restoreEventMutation.mutateAsync(id);
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to permanently delete this event? This action cannot be undone.')) {
      await deleteEventMutation.mutateAsync(id);
      router.push('/dashboard/events');
    }
  };

  if (eventError) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState
          title="Failed to load event"
          description={eventError.message}
          icon={<AlertCircle className="h-8 w-8 text-destructive" />}
          action={<Button onClick={() => refetch()}>Try again</Button>}
        />
      </div>
    );
  }

  if (isEventLoading) {
    return (
      <div className="flex flex-col h-full overflow-hidden">
        <div className="flex-none border-b bg-card px-6 py-4 animate-pulse">
          <div className="mb-4 h-4 w-24 bg-muted rounded" />
          <div className="flex items-start justify-between">
            <div className="space-y-3">
              <div className="h-8 w-64 bg-muted rounded" />
              <div className="h-4 w-48 bg-muted rounded" />
            </div>
            <div className="h-10 w-32 bg-muted rounded" />
          </div>
          <div className="flex items-center gap-6 mt-6">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-8 w-20 bg-muted rounded" />)}
          </div>
        </div>
        <div className="flex-1 p-6 flex flex-col gap-4 animate-pulse">
          <div className="h-12 w-full max-w-sm bg-muted rounded" />
          <div className="flex-1 w-full bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState
          title="Event not found"
          description="The event you are looking for does not exist or you don't have access to it."
          action={
            <Button asChild>
              <Link href="/dashboard/events">Back to Events</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const tabs = [
    { id: 'photos', label: 'Photos', icon: ImageIcon },
    { id: 'upload', label: 'Upload', icon: UploadCloud },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'share', label: 'Share', icon: Share2 },
  ];

  const handleTabChange = (tabId: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', tabId);
    router.push(`?${params.toString()}`);
  };

  const handleFolderSelect = (newFolderId: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (newFolderId) {
      params.set('folderId', newFolderId);
    } else {
      params.delete('folderId');
    }
    router.push(`?${params.toString()}`);
  };

  return (
    <ErrorBoundary>
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-none border-b bg-card px-6 py-4">
        <div className="mb-4">
          <Button variant="ghost" size="sm" asChild className="-ml-3 text-muted-foreground">
            <Link href="/dashboard/events">
              <ArrowLeft className="mr-2 h-4 w-4" /> Back to Events
            </Link>
          </Button>
        </div>
        
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight mb-2 flex items-center gap-3">
              {event.name}
              <StatusBadge status={event.status} />
            </h1>
            <p className="text-muted-foreground text-sm flex items-center gap-2">
              {event.dateEnd ? `${
                event.dateStart ? new Date(event.dateStart).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'TBD'
              } – ${
                new Date(event.dateEnd).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
              }` : (
                event.dateStart ? new Date(event.dateStart).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'TBD'
              )} · 
              <span className="capitalize">{event.eventType}</span> · 
              {event.totalPhotos.toLocaleString()} photos
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Settings className="mr-2 h-4 w-4" /> Options
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={() => setIsSettingsOpen(true)}>
                <Settings className="mr-2 h-4 w-4" />
                Event Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
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
              <DropdownMenuItem onClick={handleDelete} className="text-destructive focus:text-destructive">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Event
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-6 mt-6 border-b">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={cn(
                  "flex items-center gap-2 pb-3 text-sm font-medium transition-colors relative",
                  isActive ? "text-primary" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                {isActive && (
                  <span className="absolute bottom-0 left-0 w-full h-0.5 bg-primary rounded-t-full" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {currentTab === 'photos' && (
          <div className="flex h-full">
            {/* Left Sidebar - Folders */}
            <div className="w-64 flex-none border-r bg-muted/20">
              <FolderTree 
                eventId={id}
                folders={folders}
                activeFolderId={folderId}
                onFolderSelect={handleFolderSelect}
                isLoading={isFoldersLoading}
              />
            </div>
            
            {/* Right Content - Grid */}
            <div className="flex-1 bg-background relative">
              <PhotoGrid 
                eventId={id}
                folderId={folderId}
                onPhotoClick={setSelectedPhoto}
                onUploadClick={() => handleTabChange('upload')}
              />
            </div>
          </div>
        )}

        {currentTab === 'upload' && (
          <div className="p-8 max-w-4xl mx-auto mt-6">
            <UploadDropzone eventId={id} folders={folders} initialFolderId={folderId} />
            <UploadProgress eventId={id} />
          </div>
        )}

        {currentTab === 'analytics' && (
          <div className="space-y-8 p-4 md:p-8">
            <AnalyticsOverview eventId={id} />
            <LeadTable eventId={id} />
          </div>
        )}

        {currentTab === 'share' && event && (
          <div className="p-4 md:p-8">
            <LinkGenerator event={event} />
          </div>
        )}
      </div>

      {selectedPhoto && (
        <PhotoDetailViewer
          photo={selectedPhoto}
          eventId={id}
          onClose={() => setSelectedPhoto(null)}
        />
      )}

      {event && (
        <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Event Settings</DialogTitle>
              <DialogDescription>Update the details of your photography event</DialogDescription>
            </DialogHeader>
            <EventForm
              onSubmit={handleUpdateEvent}
              onCancel={() => setIsSettingsOpen(false)}
              isLoading={updateEventMutation.isPending}
              defaultValues={{
                name: event.name,
                eventType: event.eventType as any,
                dateStart: event.dateStart || undefined,
                dateEnd: event.dateEnd || undefined,
                description: event.description || undefined,
              }}
            />
          </DialogContent>
        </Dialog>
      )}
    </div>
    </ErrorBoundary>
  );
}
