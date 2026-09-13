import { useAuthStore } from '@/stores/auth-store';
import { ApiError } from '@/lib/api-client';

export interface DirectUploadConfig {
  eventId: string;
  file: File;
  folderId: string | null;
  onProgress: (bytesUploaded: number, bytesTotal: number) => void;
  onSuccess: () => void;
  onError: (error: Error) => void;
}

/**
 * Upload one original through FastAPI when tusd is not running locally.
 *
 * Returns an abort function so pause/cancel can stop the XHR.
 */
export function startDirectPhotoUpload(config: DirectUploadConfig): () => void {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
  const token = useAuthStore.getState().accessToken;
  const form = new FormData();
  form.append('file', config.file);
  if (config.folderId) {
    form.append('folder_id', config.folderId);
  }

  const xhr = new XMLHttpRequest();
  xhr.open('POST', `${baseUrl}/api/v1/events/${config.eventId}/photos`);
  if (token) {
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
  }

  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) {
      config.onProgress(event.loaded, event.total);
    }
  };

  xhr.onload = () => {
    if (xhr.status === 201) {
      config.onSuccess();
      return;
    }
    let message = `Upload failed (${xhr.status})`;
    let code = 'UPLOAD_FAILED';
    try {
      const body = JSON.parse(xhr.responseText) as { detail?: string; code?: string };
      if (typeof body.detail === 'string') {
        message = body.detail;
      }
      if (typeof body.code === 'string') {
        code = body.code;
      }
    } catch {
      // Keep the status-based message when the body is not JSON.
    }
    config.onError(new ApiError(xhr.status, message, code));
  };

  xhr.onerror = () => {
    config.onError(new Error('Could not reach the API to upload this photo.'));
  };

  xhr.onabort = () => {
    config.onError(new Error('Upload cancelled'));
  };

  xhr.send(form);
  return () => xhr.abort();
}
