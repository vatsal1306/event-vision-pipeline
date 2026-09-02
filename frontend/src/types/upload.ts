export type UploadStatus = 'queued' | 'uploading' | 'processing' | 'complete' | 'failed';

export interface FileProgress {
  progress: number;
  uploadedBytes: number;
  status?: UploadStatus;
  tusUploadUrl?: string;
  error?: string;
}

export interface UploadFile {
  id: string;
  file?: File; // Optional because we can't persist File objects
  targetFolderId: string;
  status: UploadStatus;
  progress: number;
  uploadedBytes: number;
  totalBytes: number;
  tusUploadUrl?: string;
  error?: string;
  retryCount: number;
}
