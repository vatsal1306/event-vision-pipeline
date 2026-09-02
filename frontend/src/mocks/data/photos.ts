import { Photo } from '@/types/event';

const RAHUL_PRIYA_EVENT_ID = 'a9b2b512-3294-4d8b-9e45-562a19ef84a1';

// Generate ~200 photos for the rahul-priya-2026 event using picsum
export const mockPhotos: Record<string, Photo[]> = {
  [RAHUL_PRIYA_EVENT_ID]: Array.from({ length: 200 }).map((_, index) => {
    // Distribute into 3 mock folders randomly
    const folderIds = ['folder-mehendi', 'folder-wedding', 'folder-reception'];
    const folderId = folderIds[index % folderIds.length];
    
    // Picsum random seed
    const seed = `photo-${index}`;
    
    return {
      id: `photo-${index}`,
      eventId: RAHUL_PRIYA_EVENT_ID,
      folderId,
      filename: `IMG_${1000 + index}.JPG`,
      originalS3Key: `events/${RAHUL_PRIYA_EVENT_ID}/originals/IMG_${1000 + index}.JPG`,
      proxyUrl: `https://picsum.photos/seed/${seed}/800/600`,
      blurhash: 'LEHV6nWB2yk8pyo0adR*.7kCMdnj', // Dummy blurhash
      width: 800,
      height: 600,
      fileSizeBytes: Math.floor(Math.random() * 5000000) + 1000000,
      mimeType: 'image/jpeg',
      faceCount: Math.floor(Math.random() * 5),
      processingStatus: 'completed',
      processingError: null,
      uploadedAt: '2026-11-23T10:00:00Z',
      createdAt: '2026-11-23T10:00:00Z',
    };
  }),
};

export const mockMatchedPhotos = mockPhotos[RAHUL_PRIYA_EVENT_ID].slice(0, 15).map(p => p.id);
