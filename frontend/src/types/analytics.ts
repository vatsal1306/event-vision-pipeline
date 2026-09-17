export interface AnalyticsSummary {
  total_views: number;
  total_downloads: number;
  total_guests: number;
  engagement_rate: number;
}

export interface AnalyticsTopPhoto {
  id: string;
  filename: string;
  proxyUrl: string | null;
  thumbUrl: string | null;
  views: number;
  downloads: number;
}

export interface GuestAnalytics {
  guest_id: string;
  guest_name: string;
  guest_phone: string;
  first_visit: string | null;
  photos_matched_count: number;
  download_count: number;
}

export interface PaginatedGuests {
  guests: GuestAnalytics[];
  total: number;
}
