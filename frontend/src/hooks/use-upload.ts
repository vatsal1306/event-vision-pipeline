import { useUploadStore } from '../stores/upload-store';
import { FileProgress } from '@/types/upload';

export const useUpload = (eventId: string) => {
  const store = useUploadStore();
  const eventState = store.events[eventId];
  
  return {
    files: eventState?.files || [],
    activeUploads: store.activeUploads,
    maxConcurrent: store.maxConcurrent,
    totalFiles: eventState?.totalFiles || 0,
    completedFiles: eventState?.completedFiles || 0,
    failedFiles: eventState?.failedFiles || 0,
    totalBytes: eventState?.totalBytes || 0,
    uploadedBytes: eventState?.uploadedBytes || 0,
    uploadSpeed: eventState?.uploadSpeed || 0,
    status: eventState?.status || 'idle',
    
    addFiles: (files: File[], targetFolderId: string) => store.addFiles(eventId, files, targetFolderId),
    removeFile: (fileId: string) => store.removeFile(eventId, fileId),
    retryFile: (fileId: string) => store.retryFile(eventId, fileId),
    pauseEvent: () => store.pauseEvent(eventId),
    resumeEvent: () => store.resumeEvent(eventId),
    cancelEvent: () => store.cancelEvent(eventId),
    updateFileProgress: (fileId: string, progress: FileProgress) => store.updateFileProgress(eventId, fileId, progress),
  };
};
