import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UploadFile, FileProgress } from '@/types/upload';

interface EventUploadState {
  files: UploadFile[];
  totalFiles: number;
  completedFiles: number;
  failedFiles: number;
  totalBytes: number;
  uploadedBytes: number;
  uploadSpeed: number;
  status: 'idle' | 'uploading' | 'paused' | 'complete' | 'error';
}

const defaultEventState: EventUploadState = {
  files: [],
  totalFiles: 0,
  completedFiles: 0,
  failedFiles: 0,
  totalBytes: 0,
  uploadedBytes: 0,
  uploadSpeed: 0,
  status: 'idle',
};

interface UploadState {
  events: Record<string, EventUploadState>;
  activeUploads: number;
  maxConcurrent: number;
  
  addFiles: (eventId: string, files: { file: File; targetFolderId: string; relativePath?: string }[]) => void;
  removeFile: (eventId: string, fileId: string) => void;
  retryFile: (eventId: string, fileId: string) => void;
  pauseEvent: (eventId: string) => void;
  resumeEvent: (eventId: string) => void;
  cancelEvent: (eventId: string) => void;
  updateFileProgress: (eventId: string, fileId: string, progress: FileProgress) => void;
}

export const useUploadStore = create<UploadState>()(
  persist(
    (set) => ({
      events: {},
      activeUploads: 0,
      maxConcurrent: 6,

  addFiles: (eventId: string, newFiles: { file: File; targetFolderId: string; relativePath?: string }[]) => {
        const uploadFiles: UploadFile[] = newFiles.map(({ file, targetFolderId, relativePath }) => ({
          id: crypto.randomUUID(),
          file, 
          relativePath,
          targetFolderId,
          status: 'queued',
          progress: 0,
          uploadedBytes: 0,
          totalBytes: file.size,
          retryCount: 0,
        }));

        set((state) => {
          const evState = state.events[eventId] || { ...defaultEventState };
          const updatedFiles = [...evState.files, ...uploadFiles];
          const newBytes = uploadFiles.reduce((acc, f) => acc + f.totalBytes, 0);
          
          return {
            events: {
              ...state.events,
              [eventId]: {
                ...evState,
                files: updatedFiles,
                totalFiles: updatedFiles.length,
                totalBytes: evState.totalBytes + newBytes,
                status: evState.status === 'idle' ? 'uploading' : evState.status,
              }
            }
          };
        });
      },

      removeFile: (eventId: string, fileId: string) => {
        set((state) => {
          const evState = state.events[eventId];
          if (!evState) return state;

          const fileToRemove = evState.files.find(f => f.id === fileId);
          if (!fileToRemove) return state;

          const newFiles = evState.files.filter((f) => f.id !== fileId);
          const wasComplete = fileToRemove.status === 'complete';
          const wasFailed = fileToRemove.status === 'failed';

          return {
            events: {
              ...state.events,
              [eventId]: {
                ...evState,
                files: newFiles,
                totalFiles: newFiles.length,
                totalBytes: evState.totalBytes - fileToRemove.totalBytes,
                uploadedBytes: evState.uploadedBytes - fileToRemove.uploadedBytes,
                completedFiles: evState.completedFiles - (wasComplete ? 1 : 0),
                failedFiles: evState.failedFiles - (wasFailed ? 1 : 0),
              }
            },
            activeUploads: fileToRemove.status === 'uploading' ? Math.max(0, state.activeUploads - 1) : state.activeUploads,
          };
        });
      },

      retryFile: (eventId: string, fileId: string) => {
        set((state) => {
          const evState = state.events[eventId];
          if (!evState) return state;

          return {
            events: {
              ...state.events,
              [eventId]: {
                ...evState,
                files: evState.files.map((f) =>
                  f.id === fileId ? { ...f, status: 'queued', error: undefined, retryCount: f.retryCount + 1 } : f
                ),
                failedFiles: Math.max(0, evState.failedFiles - 1)
              }
            }
          };
        });
      },

      pauseEvent: (eventId: string) => {
        set((state) => ({
          events: {
            ...state.events,
            [eventId]: { ...(state.events[eventId] || defaultEventState), status: 'paused' }
          }
        }));
      },

      resumeEvent: (eventId: string) => {
        set((state) => ({
          events: {
            ...state.events,
            [eventId]: { ...(state.events[eventId] || defaultEventState), status: 'uploading' }
          }
        }));
      },

      cancelEvent: (eventId: string) => {
        set((state) => {
          const newEvents = { ...state.events };
          delete newEvents[eventId];
          return { events: newEvents };
        });
      },

      updateFileProgress: (eventId: string, fileId: string, progressUpdates: FileProgress) => {
        set((state) => {
          const evState = state.events[eventId];
          if (!evState) return state;

          let deltaUploaded = 0;
          let newCompleted = evState.completedFiles;
          let newFailed = evState.failedFiles;
          let activeDelta = 0;

          const updatedFiles = evState.files.map((f) => {
            if (f.id === fileId) {
              deltaUploaded = progressUpdates.uploadedBytes - f.uploadedBytes;
              
              if (progressUpdates.status === 'uploading' && f.status !== 'uploading') activeDelta++;
              if (progressUpdates.status !== 'uploading' && f.status === 'uploading') activeDelta--;

              if (progressUpdates.status === 'complete' && f.status !== 'complete') newCompleted++;
              if (progressUpdates.status === 'failed' && f.status !== 'failed') newFailed++;
              return { ...f, ...progressUpdates };
            }
            return f;
          });

          // TODO FE-012: Actually calculate uploadSpeed based on time delta instead of static 0
          return {
            events: {
              ...state.events,
              [eventId]: {
                ...evState,
                files: updatedFiles,
                uploadedBytes: evState.uploadedBytes + Math.max(0, deltaUploaded),
                completedFiles: newCompleted,
                failedFiles: newFailed,
                uploadSpeed: 0, // TODO FE-012
              }
            },
            activeUploads: Math.max(0, state.activeUploads + activeDelta)
          };
        });
      },
    }),
    {
      name: 'upload-storage',
      partialize: (state) => {
        const persistableEvents: Record<string, EventUploadState> = {};
        for (const [eventId, evState] of Object.entries(state.events)) {
          persistableEvents[eventId] = {
            ...evState,
            files: evState.files.map(({ file, ...rest }) => rest as UploadFile),
          };
        }
        return {
          ...state,
          events: persistableEvents,
        };
      },
    }
  )
);
