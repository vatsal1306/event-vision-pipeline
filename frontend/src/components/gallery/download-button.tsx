'use client';

import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api-client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface DownloadButtonProps {
  photoId: string;
  eventId: string;
  originalFilename: string;
  className?: string;
  variant?: 'default' | 'outline' | 'ghost' | 'secondary';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  label?: string;
}

export function DownloadButton({
  photoId,
  eventId,
  originalFilename,
  className,
  variant = 'outline',
  size = 'default',
  label = 'Download',
}: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsDownloading(true);
    try {
      const { url } = await api.downloadPhoto(eventId, photoId);
      
      // Navigate to the presigned S3 URL which contains response-content-disposition=attachment
      // This forces the browser to download the file without popup blockers interfering.
      window.location.assign(url);
    } catch (error: unknown) {
      toast.error('Failed to download photo. Please try again.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <Button
      variant={variant}
      size={size}
      className={cn('', className)}
      onClick={handleDownload}
      disabled={isDownloading}
      title="Download Original"
    >
      {isDownloading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Download className="h-4 w-4" />
      )}
      {size !== 'icon' && <span className="ml-2">{label}</span>}
    </Button>
  );
}
