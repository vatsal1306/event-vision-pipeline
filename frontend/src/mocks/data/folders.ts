import { FolderNode } from '@/types/event';

const RAHUL_PRIYA_EVENT_ID = 'a9b2b512-3294-4d8b-9e45-562a19ef84a1';

export const mockFolders: Record<string, FolderNode[]> = {
  [RAHUL_PRIYA_EVENT_ID]: [
    {
      id: 'folder-mehendi',
      eventId: RAHUL_PRIYA_EVENT_ID,
      parentId: null,
      name: 'Mehndi',
      sortOrder: 1,
      createdAt: '2026-11-15T12:00:00Z',
      updatedAt: '2026-11-15T12:00:00Z',
      children: [
        {
          id: 'folder-mehendi-bride',
          eventId: RAHUL_PRIYA_EVENT_ID,
          parentId: 'folder-mehendi',
          name: 'Bride Getting Ready',
          sortOrder: 1,
          createdAt: '2026-11-15T12:00:00Z',
          updatedAt: '2026-11-15T12:00:00Z',
          children: [],
        },
        {
          id: 'folder-mehendi-guests',
          eventId: RAHUL_PRIYA_EVENT_ID,
          parentId: 'folder-mehendi',
          name: 'Guests',
          sortOrder: 2,
          createdAt: '2026-11-15T12:00:00Z',
          updatedAt: '2026-11-15T12:00:00Z',
          children: [],
        }
      ]
    },
    {
      id: 'folder-wedding',
      eventId: RAHUL_PRIYA_EVENT_ID,
      parentId: null,
      name: 'Wedding Day',
      sortOrder: 2,
      createdAt: '2026-11-15T12:00:00Z',
      updatedAt: '2026-11-15T12:00:00Z',
      children: [
        {
          id: 'folder-wedding-ceremony',
          eventId: RAHUL_PRIYA_EVENT_ID,
          parentId: 'folder-wedding',
          name: 'Ceremony',
          sortOrder: 1,
          createdAt: '2026-11-15T12:00:00Z',
          updatedAt: '2026-11-15T12:00:00Z',
          children: [],
        },
        {
          id: 'folder-wedding-couple',
          eventId: RAHUL_PRIYA_EVENT_ID,
          parentId: 'folder-wedding',
          name: 'Couple Shots',
          sortOrder: 2,
          createdAt: '2026-11-15T12:00:00Z',
          updatedAt: '2026-11-15T12:00:00Z',
          children: [],
        }
      ]
    },
    {
      id: 'folder-reception',
      eventId: RAHUL_PRIYA_EVENT_ID,
      parentId: null,
      name: 'Reception',
      sortOrder: 3,
      createdAt: '2026-11-15T12:00:00Z',
      updatedAt: '2026-11-15T12:00:00Z',
      children: []
    }
  ]
};
