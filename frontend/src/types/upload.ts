export type UploadStatus = 'queued' | 'uploading' | 'done' | 'failed';

export interface FileProgress {
  percentage: number;
  bytesUploaded: number;
  speedMBps: number;
}

export interface UploadFile {
  id: string; // UUID or unique id per file
  file: File;
  folderId: string | null;
  status: UploadStatus;
  progress: FileProgress;
  size: number;
}
