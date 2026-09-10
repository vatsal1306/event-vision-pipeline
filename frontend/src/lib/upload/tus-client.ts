import * as tus from 'tus-js-client';
import { UploadFile } from '@/types/upload';
import { CHUNK_SIZE } from '@/lib/constants';
import { guessMimeType } from '@/lib/upload/file-utils';

export interface TusUploadConfig {
  endpoint: string;
  eventId: string;
  photographerId: string;
  onProgress: (bytesUploaded: number, bytesTotal: number) => void;
  onSuccess: () => void;
  onError: (error: Error) => void;
  onUploadUrlAvailable?: (uploadUrl: string) => void;
  uploadUrl?: string;
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value
  );
}

/**
 * Build a tus-js-client upload with the metadata tusd pre-create expects.
 */
export function createTusUpload(file: UploadFile, config: TusUploadConfig): tus.Upload {
  if (!file.file) {
    throw new Error('Cannot start upload without a valid File object');
  }

  const metadata: Record<string, string> = {
    filename: file.file.name,
    filetype: guessMimeType(file.file),
    event_id: config.eventId,
    photographer_id: config.photographerId,
  };

  if (file.targetFolderId && file.targetFolderId !== 'root' && isUuid(file.targetFolderId)) {
    metadata.folder_id = file.targetFolderId;
  }

  const holder: { upload?: tus.Upload } = {};

  const options: tus.UploadOptions = {
    endpoint: config.endpoint,
    retryDelays: [0, 3000, 5000, 10000, 20000],
    metadata,
    chunkSize: CHUNK_SIZE,
    storeFingerprintForResuming: true,
    removeFingerprintOnSuccess: true,
    onError: config.onError,
    onProgress: config.onProgress,
    onSuccess: config.onSuccess,
    onUploadUrlAvailable: () => {
      config.onUploadUrlAvailable?.(holder.upload?.url || '');
    },
  };

  if (config.uploadUrl) {
    options.uploadUrl = config.uploadUrl;
  }

  holder.upload = new tus.Upload(file.file, options);
  return holder.upload;
}

/**
 * Resume a previous tus upload for the same file when a fingerprint exists.
 */
export async function startOrResumeTusUpload(upload: tus.Upload): Promise<void> {
  const previous = await upload.findPreviousUploads();
  if (previous.length > 0) {
    upload.resumeFromPreviousUpload(previous[0]);
  }
  upload.start();
}
