import { create } from 'zustand';

interface GalleryState {
  currentFolderId: string | null;
  sortBy: 'date' | 'name';
  sortOrder: 'asc' | 'desc';
  
  selectedPhotoIds: Set<string>;
  isSelecting: boolean;

  viewerOpen: boolean;
  viewerPhotoId: string | null;

  setFolder: (folderId: string | null) => void;
  setSort: (sortBy: 'date' | 'name', sortOrder: 'asc' | 'desc') => void;
  
  toggleSelect: (photoId: string) => void;
  selectAll: (photoIds: string[]) => void;
  clearSelection: () => void;
  
  openViewer: (photoId: string) => void;
  closeViewer: () => void;
}

export const useGalleryStore = create<GalleryState>((set) => ({
  currentFolderId: null,
  sortBy: 'date',
  sortOrder: 'desc',
  
  selectedPhotoIds: new Set(),
  isSelecting: false,

  viewerOpen: false,
  viewerPhotoId: null,

  setFolder: (folderId: string | null) => set({ currentFolderId: folderId, selectedPhotoIds: new Set(), isSelecting: false }),
  setSort: (sortBy: 'date' | 'name', sortOrder: 'asc' | 'desc') => set({ sortBy, sortOrder }),

  toggleSelect: (photoId: string) => set((state) => {
    const newSelection = new Set(state.selectedPhotoIds);
    if (newSelection.has(photoId)) {
      newSelection.delete(photoId);
    } else {
      newSelection.add(photoId);
    }
    return { 
      selectedPhotoIds: newSelection,
      isSelecting: newSelection.size > 0 
    };
  }),

  selectAll: (photoIds: string[]) => set({ selectedPhotoIds: new Set(photoIds), isSelecting: true }),
  clearSelection: () => set({ selectedPhotoIds: new Set(), isSelecting: false }),

  openViewer: (photoId: string) => set({ viewerOpen: true, viewerPhotoId: photoId }),
  closeViewer: () => set({ viewerOpen: false, viewerPhotoId: null }),
}));
