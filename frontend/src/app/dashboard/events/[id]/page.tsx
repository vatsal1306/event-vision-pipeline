'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams, useParams } from 'next/navigation';
import { useEvent } from '@/hooks/use-events';
import { useFolders } from '@/hooks/use-folders';
import { Photo } from '@/types/event';
import { StatusBadge } from '@/components/shared/status-badge';
import { FolderTree } from '@/components/dashboard/folder-tree';
import { PhotoGrid } from '@/components/dashboard/photo-grid';
import { PhotoDetailViewer } from '@/components/dashboard/photo-detail-viewer';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Settings, Image as ImageIcon, UploadCloud, BarChart3, Share2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function EventDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const id = params.id as string;
  const currentTab = searchParams.get('tab') || 'photos';
  const folderId = searchParams.get('folderId');

  const { data: event, isLoading: isEventLoading } = useEvent(id);
  const { data: folders = [], isLoading: isFoldersLoading } = useFolders(id);
  
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null);

  if (isEventLoading) {
    return <div className="p-8 animate-pulse text-muted-foreground">Loading event details...</div>;
  }

  if (!event) {
    return <div className="p-8 text-destructive">Event not found</div>;
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
              {event.dateStart ? new Date(event.dateStart).toLocaleDateString() : 'TBD'} · 
              <span className="capitalize">{event.eventType}</span> · 
              {event.totalPhotos.toLocaleString()} photos
            </p>
          </div>
          <Button variant="outline">
            <Settings className="mr-2 h-4 w-4" /> Event Settings
          </Button>
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
              />
            </div>
          </div>
        )}

        {currentTab === 'upload' && (
          <div className="p-8 max-w-4xl mx-auto text-center mt-12">
            <UploadCloud className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
            <h2 className="text-2xl font-semibold mb-2">Upload Interface Coming Soon</h2>
            <p className="text-muted-foreground">This tab will feature a chunked resumable uploader. (FE-012)</p>
          </div>
        )}

        {currentTab === 'analytics' && (
          <div className="p-8 max-w-4xl mx-auto text-center mt-12">
            <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
            <h2 className="text-2xl font-semibold mb-2">Analytics Coming Soon</h2>
            <p className="text-muted-foreground">This tab will show lead capture tables and event stats. (FE-013)</p>
          </div>
        )}

        {currentTab === 'share' && (
          <div className="p-8 max-w-4xl mx-auto text-center mt-12">
            <Share2 className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
            <h2 className="text-2xl font-semibold mb-2">Sharing Coming Soon</h2>
            <p className="text-muted-foreground">This tab will allow generating and configuring master/guest links. (FE-014)</p>
          </div>
        )}
      </div>

      <PhotoDetailViewer 
        photo={selectedPhoto}
        eventId={id}
        onClose={() => setSelectedPhoto(null)}
      />
    </div>
  );
}
