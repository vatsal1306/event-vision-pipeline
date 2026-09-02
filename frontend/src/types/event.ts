export type EventStatus = 'draft' | 'uploading' | 'processing' | 'ready' | 'archived';
export type EventType = 'wedding' | 'corporate' | 'birthday' | 'other';
export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface Event {
  id: string; // UUID
  photographerId: string; // UUID
  name: string;
  slug: string;
  dateStart: string | null; // ISO Date string
  dateEnd: string | null; // ISO Date string
  eventType: EventType;
  status: EventStatus;
  description: string | null;
  coverPhotoId: string | null; // UUID
  downloadEnabled: boolean;
  masterLinkActive: boolean;
  guestLinkActive: boolean;
  totalPhotos: number;
  totalFaces: number;
  processedPhotos: number;
  archiveAt: string | null; // ISO Datetime string
  createdAt: string; // ISO Datetime string
  updatedAt: string; // ISO Datetime string
}

export interface Folder {
  id: string; // UUID
  eventId: string; // UUID
  parentId: string | null; // UUID
  name: string;
  sortOrder: number;
  createdAt: string; // ISO Datetime string
  updatedAt: string; // ISO Datetime string
}

export interface FolderNode extends Folder {
  children: FolderNode[];
}

export interface Photo {
  id: string; // UUID
  eventId: string; // UUID
  folderId: string | null; // UUID
  filename: string;
  originalS3Key: string;
  proxyUrl: string | null;
  blurhash: string | null;
  width: number | null;
  height: number | null;
  fileSizeBytes: number;
  mimeType: string;
  faceCount: number;
  processingStatus: ProcessingStatus;
  processingError: string | null;
  uploadedAt: string; // ISO Datetime string
  createdAt: string; // ISO Datetime string
}
