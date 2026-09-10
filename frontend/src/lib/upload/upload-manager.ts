import { useUploadStore } from '@/stores/upload-store';
import { api } from '@/lib/api-client';
import { mapFolderNodeFromApi } from '@/lib/map-api';
import { queryClient } from '@/lib/query-client';
import { useAuthStore } from '@/stores/auth-store';
import { toast } from 'sonner';
import { createTusUpload, startOrResumeTusUpload } from '@/lib/upload/tus-client';
import * as tus from 'tus-js-client';

const TUS_ENDPOINT = process.env.NEXT_PUBLIC_TUS_ENDPOINT || '';

/**
 * Queues event photo uploads and sends them to tusd (resumable tus protocol).
 *
 * Direct FastAPI ingest (`POST /events/{id}/photos`) remains available as an
 * API fallback but is not used by the dashboard uploader.
 */
export class UploadManager {
  private static instance: UploadManager;
  private activeUploads = new Set<string>();
  private tusUploads = new Map<string, tus.Upload>();

  private constructor() {
    setInterval(() => {
      void this.processQueue();
    }, 400);
  }

  static getInstance(): UploadManager {
    if (!UploadManager.instance) {
      UploadManager.instance = new UploadManager();
    }
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
        this.startTusUpload(eventId, file.id);
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
  }

  private startTusUpload(eventId: string, fileId: string) {
    if (!TUS_ENDPOINT) {
      this.markFailed(
        eventId,
        fileId,
        'Tus endpoint is not configured. Set NEXT_PUBLIC_TUS_ENDPOINT.'
      );
      return;
    }

    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find((item) => item.id === fileId);
    const photographerId = useAuthStore.getState().photographer?.id;

    if (!file?.file || !photographerId) {
      this.markFailed(
        eventId,
        fileId,
        'Cannot start upload without a file and signed-in photographer. Re-select the files if you refreshed the page.'
      );
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
        this.markFailed(eventId, fileId, error.message);
      },
    });

    this.tusUploads.set(fileId, upload);
    void startOrResumeTusUpload(upload).catch((error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to start tus upload';
      this.markFailed(eventId, fileId, message);
    });
  }

  public async queueFiles(
    eventId: string,
    rootFolderId: string | null,
    items: { file: File; relativePath: string }[]
  ) {
    if (!TUS_ENDPOINT) {
      throw new Error(
        'Set NEXT_PUBLIC_TUS_ENDPOINT (for local: http://localhost:1080/files/) and restart Next.js.'
      );
    }

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
