'use client';

import { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface DownloadButtonProps {
  photoId: string;
  originalFilename: string;
  className?: string;
  variant?: 'default' | 'outline' | 'ghost' | 'secondary';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

export function DownloadButton({
  photoId,
  originalFilename,
  className,
  variant = 'outline',
  size = 'default',
}: DownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsDownloading(true);
    try {
      // In a real app, this might return a presigned URL or a blob.
      // Here we simulate the API call that returns a blob.
      const response = await apiClient.get(`/photos/${photoId}/download`, {
        // @ts-ignore - axios supports responseType but our local RequestOptions type omits it
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response as any]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', originalFilename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed', error);
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
      {size !== 'icon' && <span className="ml-2">Download</span>}
    </Button>
  );
}
