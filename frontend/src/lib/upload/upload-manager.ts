import { useUploadStore } from '@/stores/upload-store';
import { api } from '@/lib/api-client';
import { mapFolderNodeFromApi } from '@/lib/map-api';
import { queryClient } from '@/lib/query-client';
import { useAuthStore } from '@/stores/auth-store';
import { toast } from 'sonner';
import { createTusUpload } from '@/lib/upload/tus-client';
import { guessMimeType } from '@/lib/upload/file-utils';
import * as tus from 'tus-js-client';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';
const TUS_ENDPOINT = process.env.NEXT_PUBLIC_TUS_ENDPOINT || '';

interface InFlightDirect {
  xhr: XMLHttpRequest;
}

/**
 * Queues event photo uploads and sends them to tusd (when configured) or
 * the authenticated FastAPI ingest endpoint.
 */
export class UploadManager {
  private static instance: UploadManager;
  private activeUploads = new Set<string>();
  private directUploads = new Map<string, InFlightDirect>();
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
        if (TUS_ENDPOINT) {
          this.startTusUpload(eventId, file.id);
        } else {
          this.startDirectUpload(eventId, file.id);
        }
      }
    }
  }

  pause(eventId: string) {
    const evState = useUploadStore.getState().events[eventId];
    if (!evState) return;
    for (const file of evState.files) {
      if (file.status === 'uploading') {
        this.abortInFlight(file.id);
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
        this.abortInFlight(file.id);
        this.activeUploads.delete(file.id);
      }
    }
    useUploadStore.getState().cancelEvent(eventId);
  }

  private abortInFlight(fileId: string) {
    const direct = this.directUploads.get(fileId);
    if (direct) {
      direct.xhr.abort();
      this.directUploads.delete(fileId);
    }
    const tusUpload = this.tusUploads.get(fileId);
    if (tusUpload) {
      tusUpload.abort(true);
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
    this.directUploads.delete(fileId);
    this.tusUploads.delete(fileId);
  }

  private startDirectUpload(eventId: string, fileId: string) {
    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find((item) => item.id === fileId);

    if (!file?.file) {
      this.markFailed(eventId, fileId, 'File is no longer available. Please re-upload.');
      return;
    }

    const token = useAuthStore.getState().accessToken;
    if (!token) {
      this.markFailed(eventId, fileId, 'You are not signed in.');
      return;
    }

    store.updateFileProgress(eventId, fileId, {
      status: 'uploading',
      uploadedBytes: 0,
      progress: 0,
    });

    const formData = new FormData();
    const mime = guessMimeType(file.file);
    const blob = mime && file.file.type !== mime ? new File([file.file], file.file.name, { type: mime }) : file.file;
    formData.append('file', blob);
    if (file.targetFolderId && file.targetFolderId !== 'root') {
      formData.append('folder_id', file.targetFolderId);
    }

    const xhr = new XMLHttpRequest();
    this.directUploads.set(fileId, { xhr });

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const latest = useUploadStore.getState().events[eventId];
      if (!latest || latest.status === 'paused') return;
      useUploadStore.getState().updateFileProgress(eventId, fileId, {
        status: 'uploading',
        uploadedBytes: event.loaded,
        progress: event.loaded / event.total,
      });
    };

    xhr.onabort = () => {
      this.directUploads.delete(fileId);
      this.activeUploads.delete(fileId);
    };

    xhr.onerror = () => {
      this.markFailed(eventId, fileId, 'Network error while uploading');
    };

    xhr.onload = () => {
      this.directUploads.delete(fileId);
      this.activeUploads.delete(fileId);
      if (xhr.status >= 200 && xhr.status < 300) {
        useUploadStore.getState().updateFileProgress(eventId, fileId, {
          status: 'complete',
          uploadedBytes: file.totalBytes,
          progress: 1,
        });
        this.refreshGallery(eventId);
        return;
      }

      let message = `Upload failed (${xhr.status})`;
      try {
        const body = JSON.parse(xhr.responseText) as { detail?: unknown };
        if (typeof body.detail === 'string') {
          message = body.detail;
        }
      } catch {
        // Keep the status-based message when the body is not JSON.
      }
      this.markFailed(eventId, fileId, message);
    };

    xhr.open('POST', `${API_BASE_URL}/api/v1/events/${eventId}/photos`);
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  }

  private startTusUpload(eventId: string, fileId: string) {
    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find((item) => item.id === fileId);
    const photographerId = useAuthStore.getState().photographer?.id;

    if (!file?.file || !photographerId) {
      this.markFailed(eventId, fileId, 'Cannot start upload without a file and signed-in photographer.');
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
    upload.start();
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
