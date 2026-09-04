'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { GalleryGrid } from '@/components/gallery/gallery-grid';
import { GalleryHeader } from '@/components/gallery/gallery-header';
import { FolderNav } from '@/components/gallery/folder-nav';
import { mockEvents } from '@/mocks/data/events';
import { mockProfile } from '@/mocks/data/users';
import { mockFolders } from '@/mocks/data/folders';
import { mockPhotos } from '@/mocks/data/photos';
import { LayoutGroup } from 'framer-motion';

// Dynamic import for the viewer so it doesn't inflate the main bundle
const PhotoViewer = dynamic(
  () => import('@/components/gallery/photo-viewer').then(mod => mod.PhotoViewer),
  { ssr: false }
);

export default function GalleryDemoPage() {
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);

  const event = mockEvents[0];
  const photographer = mockProfile;
  const folders = mockFolders[event.id] || [];
  const eventPhotos = mockPhotos[event.id] || [];

  // Filter photos by selected folder
  const displayedPhotos = useMemo(() => {
    if (!selectedFolderId) return eventPhotos;
    return eventPhotos.filter((p: any) => p.folderId === selectedFolderId);
  }, [selectedFolderId, eventPhotos]);

  const handlePhotoClick = (index: number) => {
    setViewerIndex(index);
    setViewerOpen(true);
  };

  return (
    <div className="dark min-h-screen bg-background text-foreground flex flex-col">
      <GalleryHeader event={event} photographer={photographer} />

      <main className="flex-1 w-full max-w-screen-2xl mx-auto flex flex-col">
        <FolderNav
          folders={folders}
          selectedFolderId={selectedFolderId}
          onSelectFolder={setSelectedFolderId}
          className="sticky top-16 z-10 bg-background/90 backdrop-blur-sm border-b border-border/10 mb-6"
        />

        <LayoutGroup>
          <GalleryGrid
            photos={displayedPhotos}
            onPhotoClick={handlePhotoClick}
            downloadEnabled={true}
            layoutMode="guest"
            className="flex-1"
          />
        </LayoutGroup>
      </main>

      <PhotoViewer
        photos={displayedPhotos}
        currentIndex={viewerIndex}
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        onChangeIndex={setViewerIndex}
        downloadEnabled={true}
      />
    </div>
  );
}
