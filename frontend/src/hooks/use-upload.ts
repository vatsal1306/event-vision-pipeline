import { useUploadStore, FileProgress } from '../stores/upload-store';

export const useUpload = () => {
  const store = useUploadStore();
  
  return {
    files: store.files,
    activeUploads: store.activeUploads,
    maxConcurrent: store.maxConcurrent,
    totalFiles: store.totalFiles,
    completedFiles: store.completedFiles,
    failedFiles: store.failedFiles,
    totalBytes: store.totalBytes,
    uploadedBytes: store.uploadedBytes,
    uploadSpeed: store.uploadSpeed,
    status: store.status,
    
    addFiles: store.addFiles,
    removeFile: store.removeFile,
    retryFile: store.retryFile,
    pauseAll: store.pauseAll,
    resumeAll: store.resumeAll,
    cancelAll: store.cancelAll,
    updateFileProgress: store.updateFileProgress,
  };
};
