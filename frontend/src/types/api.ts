export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorDetail {
  field?: string;
  message: string;
}

export interface ApiError {
  detail: string;
  code: string;
  errors?: ApiErrorDetail[];
}

export interface TokenResponse {
  accessToken: string;
  refreshToken: string;
}

export interface AnalyticsEvent {
  id: string;
  eventId: string;
  photoId?: string;
  guestSessionId?: string;
  coupleSessionId?: string;
  action: 'view' | 'download';
  createdAt: string;
}
