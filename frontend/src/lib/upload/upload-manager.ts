import { useUploadStore } from '@/stores/upload-store';
import { api } from '@/lib/api-client';
import { mapFolderNodeFromApi } from '@/lib/map-api';
import { queryClient } from '@/lib/query-client';
import { useAuthStore } from '@/stores/auth-store';
import { toast } from 'sonner';
import { createTusUpload, startOrResumeTusUpload } from '@/lib/upload/tus-client';
import { startDirectPhotoUpload } from '@/lib/upload/direct-upload';
import { isTusdReachable, isTusdUnreachableError } from '@/lib/upload/tusd-availability';
import * as tus from 'tus-js-client';

const TUS_ENDPOINT = process.env.NEXT_PUBLIC_TUS_ENDPOINT || '';

/**
 * Queues event photo uploads. Uses tusd when it is reachable; otherwise
 * FastAPI `POST /events/{id}/photos` so local laptop uploads still work.
 */
export class UploadManager {
  private static instance: UploadManager;
  private activeUploads = new Set<string>();
  private tusUploads = new Map<string, tus.Upload>();
  private abortDirect = new Map<string, () => void>();
  private tusdReachable: boolean | null = null;

  private constructor() {
    setInterval(() => {
      void this.processQueue();
    }, 400);
  }

  static getInstance(): UploadManager {
    const globalRef = globalThis as typeof globalThis & { __spotmeUploadManager?: UploadManager };
    if (!globalRef.__spotmeUploadManager) {
      globalRef.__spotmeUploadManager = new UploadManager();
    }
    UploadManager.instance = globalRef.__spotmeUploadManager;
    return UploadManager.instance;
  }

  async processQueue() {
    const store = useUploadStore.getState();
    const { maxConcurrent, events } = store;

    for (const [eventId, evState] of Object.entries(events)) {
      if (evState.status === 'paused') continue;

      const queuedFiles = evState.files.filter((file) => file.status === 'queued');

      for (const file of queuedFiles) {
        if (useUploadStore.getState().activeUploads >= maxConcurrent) break;
        if (this.activeUploads.has(file.id)) continue;

        this.activeUploads.add(file.id);
        void this.routeUpload(eventId, file.id);
      }
    }
  }

  pause(eventId: string) {
    const evState = useUploadStore.getState().events[eventId];
    if (!evState) return;
    for (const file of evState.files) {
      if (file.status === 'uploading') {
        this.abortInFlight(file.id, false);
      }
    }
    useUploadStore.getState().pauseEvent(eventId);
  }

  resume(eventId: string) {
    useUploadStore.getState().resumeEvent(eventId);
  }

  cancel(eventId: string) {
    const evState = useUploadStore.getState().events[eventId];
    if (evState) {
      for (const file of evState.files) {
        this.abortInFlight(file.id, true);
        this.activeUploads.delete(file.id);
      }
    }
    useUploadStore.getState().cancelEvent(eventId);
  }

  private abortInFlight(fileId: string, shouldTerminate: boolean) {
    const tusUpload = this.tusUploads.get(fileId);
    if (tusUpload) {
      void tusUpload.abort(shouldTerminate);
      this.tusUploads.delete(fileId);
    }
    const abortDirect = this.abortDirect.get(fileId);
    if (abortDirect) {
      abortDirect();
      this.abortDirect.delete(fileId);
    }
    this.activeUploads.delete(fileId);
  }

  private refreshGallery(eventId: string) {
    void queryClient.invalidateQueries({ queryKey: ['event-photos', eventId] });
    void queryClient.invalidateQueries({ queryKey: ['events'] });
    void queryClient.invalidateQueries({ queryKey: ['event', eventId] });
    void queryClient.invalidateQueries({ queryKey: ['folders', eventId] });
  }

  private markFailed(eventId: string, fileId: string, error: string) {
    const store = useUploadStore.getState();
    const current = store.events[eventId]?.files.find((item) => item.id === fileId);
    store.updateFileProgress(eventId, fileId, {
      status: 'failed',
      uploadedBytes: current?.uploadedBytes ?? 0,
      progress: current ? current.uploadedBytes / current.totalBytes : 0,
      error,
    });
    this.activeUploads.delete(fileId);
    this.tusUploads.delete(fileId);
    this.abortDirect.delete(fileId);
  }

  private async ensureTusdReachable(): Promise<boolean> {
    if (this.tusdReachable !== null) {
      return this.tusdReachable;
    }
    this.tusdReachable = await isTusdReachable(TUS_ENDPOINT);
    return this.tusdReachable;
  }

  private startDirectUpload(eventId: string, fileId: string) {
    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find((item) => item.id === fileId);
    if (!file?.file) {
      this.markFailed(eventId, fileId, 'Cannot start upload without a valid file. Re-select the photos.');
      return;
    }

    store.updateFileProgress(eventId, fileId, {
      status: 'uploading',
      uploadedBytes: file.uploadedBytes,
      progress: file.totalBytes > 0 ? file.uploadedBytes / file.totalBytes : 0,
    });

    const abort = startDirectPhotoUpload({
      eventId,
      file: file.file,
      folderId: file.targetFolderId && file.targetFolderId !== 'root' ? file.targetFolderId : null,
      onProgress: (bytesUploaded, bytesTotal) => {
        useUploadStore.getState().updateFileProgress(eventId, fileId, {
          status: 'uploading',
          uploadedBytes: bytesUploaded,
          progress: bytesTotal > 0 ? bytesUploaded / bytesTotal : 0,
        });
      },
      onSuccess: () => {
        this.abortDirect.delete(fileId);
        this.activeUploads.delete(fileId);
        useUploadStore.getState().updateFileProgress(eventId, fileId, {
          status: 'complete',
          uploadedBytes: file.totalBytes,
          progress: 1,
        });
        this.refreshGallery(eventId);
      },
      onError: (error) => {
        this.abortDirect.delete(fileId);
        if (error.message === 'Upload cancelled') {
          this.activeUploads.delete(fileId);
          return;
        }
        this.markFailed(eventId, fileId, error.message);
      },
    });
    this.abortDirect.set(fileId, abort);
  }

  private async routeUpload(eventId: string, fileId: string) {
    const tusdUp = await this.ensureTusdReachable();
    if (!tusdUp) {
      this.startDirectUpload(eventId, fileId);
      return;
    }
    this.startTusUpload(eventId, fileId);
  }

  private startTusUpload(eventId: string, fileId: string) {
    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find((item) => item.id === fileId);
    const photographerId = useAuthStore.getState().photographer?.id;

    if (!file?.file) {
      this.markFailed(
        eventId,
        fileId,
        'Cannot start upload without a valid file. Re-select the photos if you refreshed the page.'
      );
      return;
    }

    if (!photographerId) {
      this.startDirectUpload(eventId, fileId);
      return;
    }

    if (!TUS_ENDPOINT) {
      this.startDirectUpload(eventId, fileId);
      return;
    }

    store.updateFileProgress(eventId, fileId, {
      status: 'uploading',
      uploadedBytes: file.uploadedBytes,
      progress: file.totalBytes > 0 ? file.uploadedBytes / file.totalBytes : 0,
    });

    const upload = createTusUpload(file, {
      endpoint: TUS_ENDPOINT,
      eventId,
      photographerId,
      uploadUrl: file.tusUploadUrl,
      onUploadUrlAvailable: (uploadUrl) => {
        useUploadStore.getState().updateFileProgress(eventId, fileId, {
          tusUploadUrl: uploadUrl,
        });
      },
      onProgress: (bytesUploaded, bytesTotal) => {
        useUploadStore.getState().updateFileProgress(eventId, fileId, {
          status: 'uploading',
          uploadedBytes: bytesUploaded,
          progress: bytesTotal > 0 ? bytesUploaded / bytesTotal : 0,
        });
      },
      onSuccess: () => {
        this.tusUploads.delete(fileId);
        this.activeUploads.delete(fileId);
        useUploadStore.getState().updateFileProgress(eventId, fileId, {
          status: 'complete',
          uploadedBytes: file.totalBytes,
          progress: 1,
        });
        this.refreshGallery(eventId);
      },
      onError: (error) => {
        this.handleTusFailure(eventId, fileId, error);
      },
    });

    this.tusUploads.set(fileId, upload);
    void startOrResumeTusUpload(upload).catch((error: unknown) => {
      this.handleTusFailure(eventId, fileId, error);
    });
  }

  /**
   * Fall back to FastAPI ingest only when tus never created a server object.
   * Mid-flight tus failures must not start a second ingest of the same file.
   */
  private handleTusFailure(eventId: string, fileId: string, error: unknown) {
    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find((item) => item.id === fileId);
    const tusUpload = this.tusUploads.get(fileId);
    const alreadyStarted =
      Boolean(tusUpload?.url) ||
      Boolean(file?.tusUploadUrl) ||
      (file?.uploadedBytes ?? 0) > 0;

    if (isTusdUnreachableError(error) && !alreadyStarted) {
      this.tusdReachable = false;
      if (tusUpload) {
        void tusUpload.abort(true);
      }
      this.tusUploads.delete(fileId);
      this.startDirectUpload(eventId, fileId);
      return;
    }

    if (tusUpload) {
      void tusUpload.abort(true);
      this.tusUploads.delete(fileId);
    }
    if (isTusdUnreachableError(error)) {
      this.tusdReachable = false;
    }
    const message = error instanceof Error ? error.message : 'Failed to upload';
    this.markFailed(eventId, fileId, message);
  }

  public async queueFiles(
    eventId: string,
    rootFolderId: string | null,
    items: { file: File; relativePath: string }[]
  ) {
    const store = useUploadStore.getState();
    const folderCache = new Map<string, string>();
    if (rootFolderId) folderCache.set('', rootFolderId);

    const filesToQueue: { file: File; targetFolderId: string | null; relativePath: string }[] = [];

    for (const item of items) {
      const parts = item.relativePath.split('/');
      parts.pop();
      const folderPath = parts.join('/');

      let currentFolderId = rootFolderId;

      if (folderPath) {
        let currentPath = '';
        let parentId = rootFolderId;

        for (const part of parts) {
          currentPath = currentPath ? `${currentPath}/${part}` : part;
          if (folderCache.has(currentPath)) {
            parentId = folderCache.get(currentPath)!;
          } else {
            try {
              const res = await api.createFolder(eventId, { name: part, parent_id: parentId });
              const created = mapFolderNodeFromApi(res as unknown as Record<string, unknown>);
              folderCache.set(currentPath, created.id);
              parentId = created.id;
            } catch {
              toast.error(`Failed to create nested folder: ${currentPath}`);
            }
          }
        }
        currentFolderId = parentId;
      }

      filesToQueue.push({
        file: item.file,
        targetFolderId: currentFolderId || null,
        relativePath: item.relativePath,
      });
    }

    store.addFiles(eventId, filesToQueue);
  }
}

export const uploadManager = UploadManager.getInstance();
