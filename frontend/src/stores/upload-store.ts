import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface UploadFile {
  id: string;
  file?: File; // Optional because we can't persist File objects
  targetFolderId: string;
  status: 'queued' | 'uploading' | 'processing' | 'complete' | 'failed';
  progress: number;
  uploadedBytes: number;
  totalBytes: number;
  tusUploadUrl?: string;
  error?: string;
  retryCount: number;
}

export interface FileProgress {
  progress: number;
  uploadedBytes: number;
  status?: UploadFile['status'];
  tusUploadUrl?: string;
  error?: string;
}

interface UploadState {
  files: UploadFile[];
  activeUploads: number;
  maxConcurrent: number;
  totalFiles: number;
  completedFiles: number;
  failedFiles: number;
  totalBytes: number;
  uploadedBytes: number;
  uploadSpeed: number;
  status: 'idle' | 'uploading' | 'paused' | 'complete' | 'error';
  
  addFiles: (files: File[], targetFolderId: string) => void;
  removeFile: (fileId: string) => void;
  retryFile: (fileId: string) => void;
  pauseAll: () => void;
  resumeAll: () => void;
  cancelAll: () => void;
  updateFileProgress: (fileId: string, progress: FileProgress) => void;
}

export const useUploadStore = create<UploadState>()(
  persist(
    (set, get) => ({
      files: [],
      activeUploads: 0,
      maxConcurrent: 6,
      totalFiles: 0,
      completedFiles: 0,
      failedFiles: 0,
      totalBytes: 0,
      uploadedBytes: 0,
      uploadSpeed: 0,
      status: 'idle',

      addFiles: (newFiles: File[], targetFolderId: string) => {
        const uploadFiles: UploadFile[] = newFiles.map((file) => ({
          id: crypto.randomUUID(),
          file, // We store the File in memory, but it won't persist
          targetFolderId,
          status: 'queued',
          progress: 0,
          uploadedBytes: 0,
          totalBytes: file.size,
          retryCount: 0,
        }));

        set((state) => {
          const updatedFiles = [...state.files, ...uploadFiles];
          return {
            files: updatedFiles,
            totalFiles: updatedFiles.length,
            totalBytes: state.totalBytes + uploadFiles.reduce((acc, f) => acc + f.totalBytes, 0),
            status: state.status === 'idle' ? 'uploading' : state.status,
          };
        });
      },

      removeFile: (fileId: string) => {
        set((state) => {
          const newFiles = state.files.filter((f) => f.id !== fileId);
          return {
            files: newFiles,
            totalFiles: newFiles.length,
          };
        });
      },

      retryFile: (fileId: string) => {
        set((state) => ({
          files: state.files.map((f) =>
            f.id === fileId ? { ...f, status: 'queued', error: undefined, retryCount: f.retryCount + 1 } : f
          ),
        }));
      },

      pauseAll: () => {
        set({ status: 'paused' });
      },

      resumeAll: () => {
        set({ status: 'uploading' });
      },

      cancelAll: () => {
        set({
          files: [],
          activeUploads: 0,
          totalFiles: 0,
          completedFiles: 0,
          failedFiles: 0,
          totalBytes: 0,
          uploadedBytes: 0,
          uploadSpeed: 0,
          status: 'idle',
        });
      },

      updateFileProgress: (fileId: string, progressUpdates: FileProgress) => {
        set((state) => {
          let deltaUploaded = 0;
          let newCompleted = state.completedFiles;
          let newFailed = state.failedFiles;

          const updatedFiles = state.files.map((f) => {
            if (f.id === fileId) {
              deltaUploaded = progressUpdates.uploadedBytes - f.uploadedBytes;
              if (progressUpdates.status === 'complete' && f.status !== 'complete') newCompleted++;
              if (progressUpdates.status === 'failed' && f.status !== 'failed') newFailed++;
              return { ...f, ...progressUpdates };
            }
            return f;
          });

          return {
            files: updatedFiles,
            uploadedBytes: state.uploadedBytes + Math.max(0, deltaUploaded),
            completedFiles: newCompleted,
            failedFiles: newFailed,
          };
        });
      },
    }),
    {
      name: 'upload-storage',
      partialize: (state) => {
        // Exclude the `file` object itself from persistence as File instances can't be stringified
        const persistableFiles = state.files.map(({ file, ...rest }) => rest);
        return {
          ...state,
          files: persistableFiles as UploadFile[],
        };
      },
    }
  )
);
