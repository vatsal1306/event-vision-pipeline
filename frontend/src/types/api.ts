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

export interface RegisterResponse {
  id: string;
  email: string;
  studio_name: string;
  phone: string;
  message: string;
}

export interface LoginOtpPendingResponse {
  otp_sent: boolean;
  phone: string;
  message: string;
  expires_in: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  photographer: import('@/types/user').Photographer;
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
