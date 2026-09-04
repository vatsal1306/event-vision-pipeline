import { useUploadStore } from '@/stores/upload-store';
import { api } from '@/lib/api-client';

import { toast } from 'sonner';
import { UploadStatus } from '@/types/upload';

const MOCK_DELAY_MS = 200;
const CHUNK_SIZE = 1024 * 512; // Simulate 512KB chunks for smooth progress

export class UploadManager {
  private static instance: UploadManager;
  private activeUploads = new Set<string>();
  private timers = new Map<string, NodeJS.Timeout>();

  private constructor() {
    // Poll the queue to start uploads
    setInterval(() => this.processQueue(), 1000);
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

    // Iterate all events (usually just one is active for uploading)
    for (const [eventId, evState] of Object.entries(events)) {
      if (evState.status === 'paused') continue;
      
      const queuedFiles = evState.files.filter(f => f.status === 'queued');
      
      for (const file of queuedFiles) {
        if (useUploadStore.getState().activeUploads >= maxConcurrent) break;
        
        if (!this.activeUploads.has(file.id)) {
          this.activeUploads.add(file.id);
          // Instead of manually updating activeUploads state directly, we just start it
          // updateFileProgress will increment activeUploads count automatically
          this.startMockUpload(eventId, file.id);
        }
      }
    }
  }

  private startMockUpload(eventId: string, fileId: string) {
    const store = useUploadStore.getState();
    const file = store.events[eventId]?.files.find(f => f.id === fileId);
    
    if (!file) {
      this.activeUploads.delete(fileId);
      return;
    }

    // Set status to uploading
    store.updateFileProgress(eventId, fileId, { status: 'uploading', uploadedBytes: file.uploadedBytes, progress: file.uploadedBytes / file.totalBytes });

    const simulateChunk = () => {
      const currentStore = useUploadStore.getState();
      const currentEvent = currentStore.events[eventId];
      if (!currentEvent || currentEvent.status === 'paused') {
        // Paused globally
        this.timers.delete(fileId);
        this.activeUploads.delete(fileId);
        return;
      }

      const currentFile = currentEvent.files.find(f => f.id === fileId);
      if (!currentFile || currentFile.status !== 'uploading') {
        // Was cancelled or paused individually
        this.timers.delete(fileId);
        this.activeUploads.delete(fileId);
        return;
      }

      let newUploaded = currentFile.uploadedBytes + CHUNK_SIZE;
      let status: UploadStatus = currentFile.status;
      
      if (newUploaded >= currentFile.totalBytes) {
        newUploaded = currentFile.totalBytes;
        status = 'complete';
      }

      // Simulate random failure (1% chance)
      if (Math.random() < 0.01 && currentFile.retryCount < 3) {
        status = 'failed';
        currentStore.updateFileProgress(eventId, fileId, {
          status: 'failed',
          uploadedBytes: currentFile.uploadedBytes,
          progress: currentFile.uploadedBytes / currentFile.totalBytes,
          error: 'Network error simulated'
        });
        
        // Auto retry logic
        setTimeout(() => {
          const s = useUploadStore.getState();
          if (s.events[eventId]?.files.find(f => f.id === fileId)?.status === 'failed') {
            s.retryFile(eventId, fileId);
          }
        }, 2000);
        
        this.timers.delete(fileId);
        this.activeUploads.delete(fileId);
        return;
      }

      currentStore.updateFileProgress(eventId, fileId, {
        status,
        uploadedBytes: newUploaded,
        progress: newUploaded / currentFile.totalBytes
      });

      if (status === 'complete') {
        this.timers.delete(fileId);
        this.activeUploads.delete(fileId);
      } else {
        const timerId = setTimeout(simulateChunk, MOCK_DELAY_MS);
        this.timers.set(fileId, timerId);
      }
    };

    const timerId = setTimeout(simulateChunk, MOCK_DELAY_MS);
    this.timers.set(fileId, timerId);
  }

  public async queueFiles(eventId: string, rootFolderId: string | null, items: { file: File, relativePath: string }[]) {
    // 1. Pre-process and create required folders
    const store = useUploadStore.getState();
    const folderCache = new Map<string, string>(); // path -> folderId
    if (rootFolderId) folderCache.set('', rootFolderId);

    const filesToQueue: { file: File, targetFolderId: string, relativePath: string }[] = [];

    for (const item of items) {
      const parts = item.relativePath.split('/');
      // The last part is the filename, the rest is the folder structure
      parts.pop(); 
      const folderPath = parts.join('/');
      
      let currentFolderId = rootFolderId;

      if (folderPath) {
        // Need to ensure this folder tree exists
        let currentPath = '';
        let parentId = rootFolderId;
        
        for (const part of parts) {
          currentPath = currentPath ? `${currentPath}/${part}` : part;
          if (folderCache.has(currentPath)) {
            parentId = folderCache.get(currentPath)!;
          } else {
            // Create folder via API
            try {
              const res = await api.createFolder(eventId, { name: part, parentId });
              folderCache.set(currentPath, res.id);
              parentId = res.id;
            } catch (err) {
              toast.error(`Failed to create nested folder: ${currentPath}`);
              // Fallback to parent
            }
          }
        }
        currentFolderId = parentId;
      }
      
      filesToQueue.push({
        file: item.file,
        targetFolderId: currentFolderId || 'root', // fallback to root string if needed
        relativePath: item.relativePath
      });
    }

    // 2. Add to store
    store.addFiles(eventId, filesToQueue);
  }
}

export const uploadManager = UploadManager.getInstance();
