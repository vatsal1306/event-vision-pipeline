import * as tus from 'tus-js-client';
import { UploadFile } from '@/types/upload';

export interface TusUploadConfig {
  endpoint: string;
  onProgress: (bytesUploaded: number, bytesTotal: number) => void;
  onSuccess: () => void;
  onError: (error: Error) => void;
  uploadUrl?: string; // If resuming
}

export function createTusUpload(file: UploadFile, config: TusUploadConfig): tus.Upload {
  if (!file.file) {
    throw new Error('Cannot start upload without a valid File object');
  }

  const options: tus.UploadOptions = {
    endpoint: config.endpoint,
    retryDelays: [0, 3000, 5000, 10000, 20000], // Auto retries
    metadata: {
      filename: file.file.name,
      filetype: file.file.type,
      targetFolderId: file.targetFolderId,
    },
    onError: config.onError,
    onProgress: config.onProgress,
    onSuccess: config.onSuccess,
    chunkSize: 5 * 1024 * 1024, // 5MB
  };

  if (config.uploadUrl) {
    options.uploadUrl = config.uploadUrl;
  }

  return new tus.Upload(file.file, options);
}
