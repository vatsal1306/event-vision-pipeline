import { http, HttpResponse, delay } from 'msw';
import { v4 as uuidv4 } from 'uuid';
import { mockEvents } from './data/events';
import { mockPhotos, mockMatchedPhotos } from './data/photos';
import { mockFolders } from './data/folders';
import { mockProfile } from './data/users';
import { mockAnalyticsSummary, mockAnalyticsTopPhotos } from './data/analytics';
import { EventType } from '@/types/event';

export const handlers = [
  // ==========================================
  // NOTE: Partial API Coverage
  // Handlers for some §10.2 paths (e.g. detailed folders CRUD, settings, master link sharing)
  // are intentionally omitted here. They will be added as the respective UI screens land.
  // ==========================================

  // Event list
  http.get('*/api/events', () => {
    return HttpResponse.json({
      items: mockEvents,
      total: mockEvents.length,
      limit: 50,
      offset: 0,
      hasMore: false,
    });
  }),

  // Create event
  http.post('*/api/events', async ({ request }) => {
    const data = await request.json() as {
      name: string;
      dateStart: string;
      dateEnd?: string;
      eventType: EventType;
      description?: string;
    };
    await delay(800);

    const now = new Date().toISOString();
    const newEvent = {
      id: uuidv4(),
      photographerId: 'photog-1234',
      name: data.name,
      slug: data.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') + '-' + Date.now().toString(36),
      dateStart: data.dateStart,
      dateEnd: data.dateEnd || null,
      eventType: data.eventType,
      status: 'draft' as const,
      description: data.description || null,
      coverPhotoId: null,
      downloadEnabled: false,
      masterLinkActive: false,
      guestLinkActive: false,
      totalPhotos: 0,
      totalFaces: 0,
      processedPhotos: 0,
      guestCount: 0,
      folderCount: 0,
      archiveAt: null,
      createdAt: now,
      updatedAt: now,
    };

    mockEvents.unshift(newEvent);

    return HttpResponse.json(newEvent, { status: 201 });
  }),

  // Get specific event details
  http.get('*/api/events/:id', ({ params }) => {
    const event = mockEvents.find(e => e.id === params.id);
    if (!event) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(event);
  }),

  // Photo list with pagination and folder filtering
  http.get('*/api/events/:id/photos', ({ request, params }) => {
    const url = new URL(request.url);
    const offset = parseInt(url.searchParams.get('offset') || '0');
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const folderId = url.searchParams.get('folderId');

    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    let photos = mockPhotos[eventId] || [];
    if (folderId) {
      photos = photos.filter(p => p.folderId === folderId);
    }

    return HttpResponse.json({
      items: photos.slice(offset, offset + limit),
      total: photos.length,
      limit,
      offset,
      hasMore: offset + limit < photos.length,
    });
  }),

  // Folder list
  http.get('*/api/events/:id/folders', ({ params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    return HttpResponse.json(mockFolders[eventId] || []);
  }),

  // Create folder
  http.post('*/api/events/:id/folders', async ({ request, params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const data = await request.json() as any;
    const newFolder = {
      id: `folder-${Date.now()}`,
      eventId,
      parentId: data.parentId || null,
      name: data.name,
      sortOrder: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      children: [],
    };
    
    if (!mockFolders[eventId]) {
      mockFolders[eventId] = [];
    }

    if (data.parentId) {
      // Helper to find and add
      const addChild = (nodes: any[]) => {
        for (const node of nodes) {
          if (node.id === data.parentId) {
            node.children = node.children || [];
            node.children.push(newFolder);
            return true;
          }
          if (node.children && addChild(node.children)) return true;
        }
        return false;
      };
      addChild(mockFolders[eventId]);
    } else {
      mockFolders[eventId].push(newFolder);
    }
    
    return HttpResponse.json(newFolder, { status: 201 });
  }),

  // Rename folder
  http.put('*/api/events/:id/folders/:folderId', async ({ request, params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const folderId = Array.isArray(params.folderId) ? params.folderId[0] : params.folderId;
    const data = await request.json() as any;
    
    if (mockFolders[eventId]) {
      const rename = (nodes: any[]) => {
        for (const node of nodes) {
          if (node.id === folderId) {
            node.name = data.name;
            return true;
          }
          if (node.children && rename(node.children)) return true;
        }
        return false;
      };
      rename(mockFolders[eventId]);
    }

    return HttpResponse.json({ name: data.name });
  }),

  // Delete folder
  http.delete('*/api/events/:id/folders/:folderId', ({ params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const folderId = Array.isArray(params.folderId) ? params.folderId[0] : params.folderId;
    
    if (mockFolders[eventId]) {
      const del = (nodes: any[]): any[] => {
        return nodes.filter(node => {
          if (node.id === folderId) return false;
          if (node.children) node.children = del(node.children);
          return true;
        });
      };
      mockFolders[eventId] = del(mockFolders[eventId]);
    }

    return new HttpResponse(null, { status: 204 });
  }),

  // Move photos
  http.post('*/api/events/:id/photos/move', async ({ request, params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const data = await request.json() as any;
    
    if (mockPhotos[eventId]) {
      mockPhotos[eventId] = mockPhotos[eventId].map(p => {
        if (data.photoIds.includes(p.id)) {
          return { ...p, folderId: data.targetFolderId };
        }
        return p;
      });
    }

    return new HttpResponse(null, { status: 200 });
  }),

  // Delete photo
  http.delete('*/api/events/:id/photos/:photoId', ({ params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const photoId = Array.isArray(params.photoId) ? params.photoId[0] : params.photoId;
    
    if (mockPhotos[eventId]) {
      mockPhotos[eventId] = mockPhotos[eventId].filter(p => p.id !== photoId);
    }
    
    return new HttpResponse(null, { status: 204 });
  }),

  // Guest selfie → simulated match
  http.post('*/api/event/:slug/selfie', async () => {
    // Simulate processing delay of ~1500ms
    await delay(1500);
    return HttpResponse.json({
      matchedPhotoIds: mockMatchedPhotos,
      matchCount: mockMatchedPhotos.length,
    });
  }),

  // Photographer Auth
  http.post('*/api/auth/login', async ({ request }) => {
    const data = await request.json() as any;
    await delay(800);
    if (data.email === 'admin@spotme.com' && data.password === 'Password123!') {
      return HttpResponse.json({ accessToken: 'photographer_token', refreshToken: 'photographer_refresh' });
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
  }),

  http.post('*/api/auth/register', async () => {
    await delay(800);
    // return success, expects OTP next
    return HttpResponse.json({ detail: 'OTP sent to mobile' });
  }),
  
  http.post('*/api/auth/verify-otp', async ({ request }) => {
    const data = await request.json() as { code?: string };
    await delay(800);
    if (data.code === '123456') {
      return HttpResponse.json({ accessToken: 'photographer_token', refreshToken: 'photographer_refresh' });
    }
    return HttpResponse.json({ detail: 'Invalid code', code: 'INVALID_OTP' }, { status: 400 });
  }),

  http.post('*/api/auth/forgot-password', async () => {
    await delay(500);
    return HttpResponse.json({ detail: 'Reset link sent' });
  }),

  // Mock guest auth / OTP validation
  http.post('*/api/event/:slug/auth', async () => {
    // Send OTP stub
    await delay(500);
    return HttpResponse.json({ detail: 'OTP sent' });
  }),
  
  http.post('*/api/event/:slug/auth/verify', async ({ request }) => {
    const data = await request.json() as { code?: string };
    
    // Simulate network delay
    await delay(500);

    if (data.code === '123456') {
      return HttpResponse.json({ accessToken: 'mock_guest_token', refreshToken: 'mock_refresh' });
    }
    
    return HttpResponse.json({ 
      detail: 'Invalid code',
      code: 'INVALID_OTP'
    }, { status: 400 });
  }),

  // Fallback upload URL mock
  http.post('*/api/upload/create', () => {
    return HttpResponse.json({
      uploadUrl: 'https://mock.upload.url'
    });
  }),

  // Profile
  http.get('*/api/profile', () => {
    return HttpResponse.json(mockProfile);
  }),

  // Analytics
  http.get('*/api/events/:id/analytics/summary', () => {
    return HttpResponse.json(mockAnalyticsSummary);
  }),

  http.get('*/api/events/:id/analytics/top-photos', () => {
    return HttpResponse.json(mockAnalyticsTopPhotos);
  })
];
