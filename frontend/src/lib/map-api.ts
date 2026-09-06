import { Event, EventStatus, EventType, FolderNode } from '@/types/event';

export function mapEventFromApi(raw: Record<string, unknown>): Event {
  return {
    id: String(raw.id),
    photographerId: String(raw.photographer_id ?? ''),
    name: String(raw.name),
    slug: String(raw.slug),
    dateStart: (raw.date_start as string | null) ?? null,
    dateEnd: (raw.date_end as string | null) ?? null,
    eventType: (raw.event_type as EventType) ?? 'wedding',
    status: (raw.status as EventStatus) ?? 'draft',
    description: (raw.description as string | null) ?? null,
    coverPhotoId: (raw.cover_photo_id as string | null) ?? null,
    downloadEnabled: Boolean(raw.download_enabled ?? true),
    masterLinkActive: Boolean(raw.master_link_active ?? true),
    guestLinkActive: Boolean(raw.guest_link_active ?? true),
    totalPhotos: Number(raw.total_photos ?? 0),
    totalFaces: Number(raw.total_faces ?? 0),
    processedPhotos: Number(raw.processed_photos ?? 0),
    guestCount: Number(raw.guest_count ?? 0),
    folderCount: Number(raw.folder_count ?? 0),
    archiveAt: (raw.archive_at as string | null) ?? null,
    createdAt: String(raw.created_at ?? new Date().toISOString()),
    updatedAt: String(raw.updated_at ?? raw.created_at ?? new Date().toISOString()),
  };
}

export function mapFolderNodeFromApi(raw: Record<string, unknown>): FolderNode {
  const children = Array.isArray(raw.children)
    ? raw.children.map((child) => mapFolderNodeFromApi(child as Record<string, unknown>))
    : [];
  return {
    id: String(raw.id),
    eventId: String(raw.event_id),
    parentId: (raw.parent_id as string | null) ?? null,
    name: String(raw.name),
    sortOrder: Number(raw.sort_order ?? 0),
    createdAt: String(raw.created_at ?? new Date().toISOString()),
    updatedAt: String(raw.updated_at ?? raw.created_at ?? new Date().toISOString()),
    children,
    photoCount: typeof raw.photo_count === 'number' ? raw.photo_count : undefined,
  };
}
