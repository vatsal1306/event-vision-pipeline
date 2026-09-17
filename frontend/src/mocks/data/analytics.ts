export const mockAnalyticsSummary = {
  total_views: 4500,
  total_downloads: 1200,
  total_guests: 350,
  engagement_rate: 85,
};

export const mockAnalyticsTopPhotos = {
  photos: [
    { id: 'photo-1', filename: 'photo-1.jpg', proxy_url: 'https://picsum.photos/seed/photo-1/2048/2048', thumb_url: 'https://picsum.photos/seed/photo-1/480/480', views: 300, downloads: 150 },
    { id: 'photo-2', filename: 'photo-2.jpg', proxy_url: 'https://picsum.photos/seed/photo-2/2048/2048', thumb_url: 'https://picsum.photos/seed/photo-2/480/480', views: 250, downloads: 120 },
    { id: 'photo-3', filename: 'photo-3.jpg', proxy_url: 'https://picsum.photos/seed/photo-3/2048/2048', thumb_url: 'https://picsum.photos/seed/photo-3/480/480', views: 200, downloads: 90 },
  ]
};

export const mockGuestAnalytics = Array.from({ length: 50 }).map((_, i) => ({
  guest_id: `guest-${i + 1}`,
  guest_name: `Guest Name ${i + 1}`,
  guest_phone: `+15550100${i.toString().padStart(2, '0')}`,
  first_visit: new Date(Date.now() - Math.random() * 10000000000).toISOString(),
  photos_matched_count: Math.floor(Math.random() * 20),
  download_count: Math.floor(Math.random() * 10),
}));
