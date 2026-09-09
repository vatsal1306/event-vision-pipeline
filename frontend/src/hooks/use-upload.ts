import { useUploadStore } from '../stores/upload-store';
import { FileProgress } from '@/types/upload';
import { uploadManager } from '@/lib/upload/upload-manager';

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
    
    addFiles: (files: { file: File; targetFolderId: string; relativePath?: string }[]) => store.addFiles(eventId, files),
    removeFile: (fileId: string) => store.removeFile(eventId, fileId),
    retryFile: (fileId: string) => store.retryFile(eventId, fileId),
    pauseEvent: () => uploadManager.pause(eventId),
    resumeEvent: () => uploadManager.resume(eventId),
    cancelEvent: () => uploadManager.cancel(eventId),
    updateFileProgress: (fileId: string, progress: FileProgress) => store.updateFileProgress(eventId, fileId, progress),
  };
};
