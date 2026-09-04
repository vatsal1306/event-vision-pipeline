import { http, HttpResponse, delay } from 'msw';
import { v4 as uuidv4 } from 'uuid';
import { mockEvents } from './data/events';
import { mockPhotos, mockMatchedPhotos } from './data/photos';
import { mockFolders } from './data/folders';
import { mockProfile } from './data/users';
import { mockAnalyticsSummary, mockAnalyticsTopPhotos, mockGuestAnalytics } from './data/analytics';
import { Event, EventType } from '@/types/event';
import { Photographer } from '@/types/user';

// Mock state for favorites
const mockedFavorites = new Set<string>();

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

  // Toggle link (Master / Guest)
  http.put('*/api/events/:id/links/:type/toggle', ({ params }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const eventIndex = mockEvents.findIndex(e => e.id === eventId);
    if (eventIndex === -1) return new HttpResponse(null, { status: 404 });
    
    const rawType = Array.isArray(params.type) ? params.type[0] : params.type;
    const type = rawType as 'master' | 'guest';
    if (type === 'master') {
      mockEvents[eventIndex].masterLinkActive = !mockEvents[eventIndex].masterLinkActive;
    } else if (type === 'guest') {
      mockEvents[eventIndex].guestLinkActive = !mockEvents[eventIndex].guestLinkActive;
    }

    return HttpResponse.json(null, { status: 200 });
  }),

  // Update Event Settings
  http.put('*/api/events/:id/settings', async ({ params, request }) => {
    const eventId = Array.isArray(params.id) ? params.id[0] : params.id;
    const eventIndex = mockEvents.findIndex(e => e.id === eventId);
    if (eventIndex === -1) return new HttpResponse(null, { status: 404 });
    
    const body = await request.json() as Partial<Event>;
    mockEvents[eventIndex] = { ...mockEvents[eventIndex], ...body };

    return HttpResponse.json(mockEvents[eventIndex]);
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
  
  http.put('*/api/profile', async ({ request }) => {
    const body = await request.json() as Partial<Photographer>;
    Object.assign(mockProfile, body);
    return HttpResponse.json(mockProfile);
  }),

  http.post('*/api/profile/logo', () => {
    mockProfile.logoUrl = `https://picsum.photos/seed/${uuidv4()}/200/200`;
    return HttpResponse.json({ url: mockProfile.logoUrl });
  }),

  http.post('*/api/profile/watermark', () => {
    mockProfile.watermarkUrl = `https://picsum.photos/seed/${uuidv4()}/400/200`;
    return HttpResponse.json({ url: mockProfile.watermarkUrl });
  }),

  http.get('*/api/profile/storage', () => {
    return HttpResponse.json({
      used: mockProfile.storageUsedBytes,
      limit: mockProfile.storageLimitBytes,
    });
  }),

  // Analytics
  http.get('*/api/events/:id/analytics/summary', () => {
    return HttpResponse.json(mockAnalyticsSummary);
  }),

  http.get('*/api/events/:id/analytics/top-photos', () => {
    return HttpResponse.json(mockAnalyticsTopPhotos);
  }),

  http.get('*/api/events/:id/analytics/guests', ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1', 10);
    const limit = parseInt(url.searchParams.get('limit') || '10', 10);
    const sortBy = url.searchParams.get('sortBy') || 'guest_name';
    const sortOrder = url.searchParams.get('sortOrder') || 'asc';

    let sorted = [...mockGuestAnalytics];
    
    sorted.sort((a, b) => {
      let valA = a[sortBy as keyof typeof a];
      let valB = b[sortBy as keyof typeof b];
      
      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortOrder === 'asc' ? valA - valB : valB - valA;
      }
      
      return 0;
    });

    const start = (page - 1) * limit;
    const end = start + limit;
    const paginated = sorted.slice(start, end);

    return HttpResponse.json({
      guests: paginated,
      total: sorted.length
    });
  }),
  // ==========================================
  // Public / Master Link Endpoints
  // ==========================================

  http.get('*/api/event/:slug/info', ({ params }) => {
    const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
    const event = mockEvents.find(e => e.slug === slug);
    
    if (!event) {
      return new HttpResponse(null, { status: 404 });
    }
    
    return HttpResponse.json({
      event,
      photographer: mockProfile
    });
  }),

  http.post('*/api/event/:slug/master/auth', async () => {
    await delay(500);
    return HttpResponse.json({ success: true });
  }),

  http.post('*/api/event/:slug/master/verify', async ({ request }) => {
    const data = await request.json() as { otp: string };
    await delay(500);
    
    if (data.otp === '123456') {
      return HttpResponse.json({ token: `mock-master-token-${Date.now()}` });
    }
    return new HttpResponse(JSON.stringify({ message: 'Invalid OTP' }), { status: 400 });
  }),

  http.get('*/api/event/:slug/master/folders', ({ params }) => {
    const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
    const event = mockEvents.find(e => e.slug === slug);
    
    if (!event) return new HttpResponse(null, { status: 404 });
    
    const folders = mockFolders[event.id] || [];
    return HttpResponse.json(folders);
  }),

  http.get('*/api/event/:slug/master/photos', ({ params }) => {
    const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
    const event = mockEvents.find(e => e.slug === slug);
    
    if (!event) return new HttpResponse(null, { status: 404 });
    
    const photos = mockPhotos[event.id] || [];
    return HttpResponse.json(photos);
  }),

  http.get('*/api/event/:slug/master/favorites', ({ params }) => {
    const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
    const event = mockEvents.find(e => e.slug === slug);
    
    if (!event) return new HttpResponse(null, { status: 404 });
    
    const photos = mockPhotos[event.id] || [];
    const favoritePhotos = photos.filter(p => mockedFavorites.has(p.id));
    return HttpResponse.json(favoritePhotos);
  }),

  http.post('*/api/event/:slug/master/favorite', async ({ request, params }) => {
    const data = await request.json() as { photoId: string };
    
    if (mockedFavorites.has(data.photoId)) {
      mockedFavorites.delete(data.photoId);
    } else {
      mockedFavorites.add(data.photoId);
    }
    
    return HttpResponse.json({ success: true });
  }),

  // ==========================================
  // Guest Link Endpoints
  // ==========================================

  http.post('*/api/event/:slug/auth', async () => {
    await delay(500);
    return HttpResponse.json({ success: true });
  }),

  http.post('*/api/event/:slug/auth/verify', async ({ request }) => {
    const data = await request.json() as { otp: string };
    await delay(500);
    
    if (data.otp === '123456') {
      return HttpResponse.json({ 
        accessToken: `mock-guest-token-${Date.now()}`,
        refreshToken: `mock-refresh-token`
      });
    }
    return new HttpResponse(JSON.stringify({ message: 'Invalid OTP' }), { status: 400 });
  }),

  http.post('*/api/event/:slug/selfie', async () => {
    // Simulate processing time
    await delay(2500);
    // Return mock matches (e.g. 5 random photos)
    return HttpResponse.json({ 
      matchedPhotoIds: ['mock-1', 'mock-2'], 
      matchCount: 5 
    });
  }),

  http.get('*/api/event/:slug/guest/photos', ({ params }) => {
    const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
    const event = mockEvents.find(e => e.slug === slug);
    
    if (!event) return new HttpResponse(null, { status: 404 });
    
    const photos = mockPhotos[event.id] || [];
    // Mock matching photos (take first 5)
    const matchedPhotos = photos.slice(0, 5);
    
    return HttpResponse.json({
      items: matchedPhotos, // Depending on PaginatedResponse structure, maybe data or items? Let's assume data/items. The types will tell if there's an error. 
      total: matchedPhotos.length,
      page: 1,
      limit: 20,
      totalPages: 1
    });
  }),
];
