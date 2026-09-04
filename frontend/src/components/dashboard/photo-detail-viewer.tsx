import React from 'react';
import { ResponsiveImage } from '@/components/shared/responsive-image';
import { Photo, FolderNode } from '@/types/event';
import { useDeletePhotos } from '@/hooks/use-event-photos';
import { useFolders } from '@/hooks/use-folders';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Trash2, Download, Maximize, Calendar, Hash, FolderOpen, Image as ImageIcon } from 'lucide-react';
import { toast } from 'sonner';

interface PhotoDetailViewerProps {
  photo: Photo | null;
  eventId: string;
  onClose: () => void;
}

export function PhotoDetailViewer({ photo, eventId, onClose }: PhotoDetailViewerProps) {
  const { data: folders = [] } = useFolders(eventId);
  const deleteMutation = useDeletePhotos(eventId);

  if (!photo) return null;

  // Helper to find folder path
  const getFolderPath = (folderId: string | null, nodes: FolderNode[], path: string[] = []): string[] => {
    if (!folderId) return ['All Photos'];
    
    for (const node of nodes) {
      if (node.id === folderId) {
        return [...path, node.name];
      }
      if (node.children) {
        const found = getFolderPath(folderId, node.children, [...path, node.name]);
        if (found.length > 0 && found[found.length - 1] !== 'All Photos') {
          return found;
        }
      }
    }
    return [];
  };

  const folderPath = getFolderPath(photo.folderId, folders).join(' / ') || 'All Photos';

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this photo?')) return;
    try {
      await deleteMutation.mutateAsync([photo.id]);
      toast.success('Photo deleted');
      onClose();
    } catch {
      toast.error('Failed to delete photo');
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Sheet open={!!photo} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-md md:max-w-lg lg:max-w-xl overflow-y-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="truncate">{photo.filename}</SheetTitle>
          <SheetDescription>
            Metadata Inspector
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6">
          {/* Preview Image */}
          <div className="relative aspect-auto bg-muted rounded-lg overflow-hidden border border-border flex items-center justify-center min-h-[300px]">
            {photo.proxyUrl ? (
              <ResponsiveImage
                src={photo.proxyUrl}
                alt={photo.filename}
                blurhash={photo.blurhash}
                width={800}
                height={600}
                className="w-full h-auto max-h-[60vh]"
                imageClassName="object-contain"
                unoptimized
              />
            ) : (
              <ImageIcon className="h-12 w-12 text-muted-foreground" />
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button variant="outline" className="flex-1" asChild>
              <a href={photo.proxyUrl || '#'} target="_blank" rel="noopener noreferrer">
                <Download className="mr-2 h-4 w-4" /> Download Proxy
              </a>
            </Button>
            <Button variant="destructive" className="flex-1" onClick={handleDelete}>
              <Trash2 className="mr-2 h-4 w-4" /> Delete Photo
            </Button>
          </div>

          {/* Metadata details */}
          <div className="bg-muted/50 rounded-lg p-4 space-y-4">
            <h4 className="font-semibold text-sm border-b pb-2">Properties</h4>
            
            <div className="grid grid-cols-3 gap-y-4 gap-x-2 text-sm">
              <div className="col-span-1 text-muted-foreground flex items-center gap-2">
                <Hash className="h-4 w-4" /> ID
              </div>
              <div className="col-span-2 font-mono text-xs break-all">{photo.id}</div>

              <div className="col-span-1 text-muted-foreground flex items-center gap-2">
                <FolderOpen className="h-4 w-4" /> Folder
              </div>
              <div className="col-span-2">{folderPath}</div>

              <div className="col-span-1 text-muted-foreground flex items-center gap-2">
                <Maximize className="h-4 w-4" /> Dimensions
              </div>
              <div className="col-span-2">
                {photo.width && photo.height ? `${photo.width} × ${photo.height}` : 'Unknown'}
              </div>

              <div className="col-span-1 text-muted-foreground flex items-center gap-2">
                <ImageIcon className="h-4 w-4" /> File Size
              </div>
              <div className="col-span-2">{formatBytes(photo.fileSizeBytes)}</div>

              <div className="col-span-1 text-muted-foreground flex items-center gap-2">
                <Calendar className="h-4 w-4" /> Uploaded
              </div>
              <div className="col-span-2">{formatDate(photo.uploadedAt)}</div>

              <div className="col-span-1 text-muted-foreground flex items-center gap-2">
                👤 Faces
              </div>
              <div className="col-span-2">{photo.faceCount} detected</div>
            </div>
          </div>

          {/* S3 info (internal) */}
          <div className="bg-muted/30 rounded-lg p-4">
             <h4 className="font-semibold text-sm border-b pb-2 mb-3">Storage Link</h4>
             <p className="font-mono text-[10px] break-all text-muted-foreground">
               {photo.originalS3Key}
             </p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
