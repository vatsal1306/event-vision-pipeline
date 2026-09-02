'use client';

import { useState } from 'react';
import { mockPhotos } from '@/mocks/data/photos';
import { mockEvents } from '@/mocks/data/events';
import { mockProfile } from '@/mocks/data/users';
import { Folder } from '@/types/event';
import { GalleryGrid } from '@/components/gallery/gallery-grid';
import { GalleryHeader } from '@/components/gallery/gallery-header';
import { FolderNav } from '@/components/gallery/folder-nav';
import { PhotoViewer } from '@/components/gallery/photo-viewer';

export default function GalleryDemoPage() {
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);
  
  const event = mockEvents[0];
  const photographer = mockProfile;
  const folders: Folder[] = [
    { id: 'folder-mehendi', eventId: event.id, parentId: null, name: 'Mehendi', sortOrder: 0, createdAt: '', updatedAt: '' },
    { id: 'folder-wedding', eventId: event.id, parentId: null, name: 'Wedding', sortOrder: 1, createdAt: '', updatedAt: '' },
    { id: 'folder-reception', eventId: event.id, parentId: null, name: 'Reception', sortOrder: 2, createdAt: '', updatedAt: '' }
  ];
  
  const allPhotos = mockPhotos[event.id] || [];

  // Filter photos by selected folder
  const displayedPhotos = selectedFolderId 
    ? allPhotos.filter(p => p.folderId === selectedFolderId)
    : allPhotos;

  return (
    <div className="min-h-screen bg-background">
      <GalleryHeader event={event} photographer={photographer} />
      
      <main className="container mx-auto">
        <FolderNav 
          folders={folders} 
          selectedFolderId={selectedFolderId} 
          onSelectFolder={setSelectedFolderId} 
          className="my-4 sticky top-16 bg-background z-10"
        />
        
        <GalleryGrid 
          photos={displayedPhotos} 
          onPhotoClick={setViewerIndex} 
        />
      </main>

      <PhotoViewer
        photos={displayedPhotos}
        currentIndex={viewerIndex ?? 0}
        isOpen={viewerIndex !== null}
        onClose={() => setViewerIndex(null)}
        onChangeIndex={setViewerIndex}
      />
    </div>
  );
}
