'use client';

import { useAnalyticsSummary, useTopPhotos } from '@/hooks/use-analytics';
import { ResponsiveImage } from '@/components/shared/responsive-image';
import { Users, Eye, Download } from 'lucide-react';

interface AnalyticsOverviewProps {
  eventId: string;
}

export function AnalyticsOverview({ eventId }: AnalyticsOverviewProps) {
  const { data: summary, isLoading: isSummaryLoading } = useAnalyticsSummary(eventId);
  const { data: topPhotosData, isLoading: isPhotosLoading } = useTopPhotos(eventId);

  if (isSummaryLoading) {
    return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading analytics...</div>;
  }

  if (!summary) {
    return <div className="p-8 text-center text-muted-foreground">Failed to load analytics data.</div>;
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between space-y-0 pb-2">
            <h3 className="tracking-tight text-sm font-medium">Total Guests</h3>
            <Users className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-bold">{summary.total_guests}</div>
          <p className="text-xs text-muted-foreground mt-1">Unique visitors</p>
        </div>

        <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between space-y-0 pb-2">
            <h3 className="tracking-tight text-sm font-medium">Total Views</h3>
            <Eye className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-bold">{summary.total_views}</div>
          <p className="text-xs text-muted-foreground mt-1">Across all galleries</p>
        </div>

        <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-6 flex flex-col justify-between">
          <div className="flex items-center justify-between space-y-0 pb-2">
            <h3 className="tracking-tight text-sm font-medium">Total Downloads</h3>
            <Download className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="text-2xl font-bold">{summary.total_downloads}</div>
          <p className="text-xs text-muted-foreground mt-1">Photos saved by guests</p>
        </div>
      </div>

      <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-6">
        <h3 className="text-lg font-semibold mb-4">Top Viewed Photos</h3>
        {isPhotosLoading ? (
          <div className="h-40 flex items-center justify-center text-muted-foreground animate-pulse">
            Loading top photos...
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {topPhotosData?.photos.map((photo: import('@/types/analytics').AnalyticsTopPhoto) => (
              <div key={photo.photoId} className="group relative rounded-md overflow-hidden border">
                <ResponsiveImage
                  src={`https://picsum.photos/seed/${photo.photoId}/400/400`}
                  alt={`Top photo ${photo.photoId}`}
                  aspectRatio={1}
                />
                <div className="absolute bottom-0 left-0 right-0 bg-black/60 p-2 text-white text-xs flex justify-between items-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {photo.views}</span>
                  <span className="flex items-center gap-1"><Download className="h-3 w-3" /> {photo.downloads}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
