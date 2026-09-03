import React, { useRef, useEffect, useState, useMemo } from 'react';
import Image from 'next/image';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useEventPhotos, useMovePhotos, useDeletePhotos } from '@/hooks/use-event-photos';
import { useFolders } from '@/hooks/use-folders';
import { Photo, FolderNode } from '@/types/event';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuPortal,
  DropdownMenuSubContent,
} from '@/components/ui/dropdown-menu';
import { Loader2, Move, Trash2, X, FolderOpen, Image as ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface PhotoGridProps {
  eventId: string;
  folderId: string | null;
  onPhotoClick: (photo: Photo) => void;
}

export function PhotoGrid({ eventId, folderId, onPhotoClick }: PhotoGridProps) {
  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useEventPhotos(eventId, folderId);
  const { data: folders = [] } = useFolders(eventId);
  
  const moveMutation = useMovePhotos(eventId);
  const deleteMutation = useDeletePhotos(eventId);

  const [selectedPhotoIds, setSelectedPhotoIds] = useState<Set<string>>(new Set());
  const parentRef = useRef<HTMLDivElement>(null);

  // Flatten infinite query pages into a single array
  const photos = useMemo(() => {
    return data?.pages.flatMap(page => page.items) ?? [];
  }, [data]);

  // Responsive columns (naive approach for a resize-aware grid, you'd ideally use a ResizeObserver on parentRef)
  const columns = 4;
  const count = photos.length;

  const rowVirtualizer = useVirtualizer({
    count: Math.ceil(count / columns),
    getScrollElement: () => parentRef.current,
    estimateSize: () => 250, // Approx height of a row
    overscan: 5,
  });

  // Infinite scroll observer
  useEffect(() => {
    const scrollElement = parentRef.current;
    if (!scrollElement) return;

    const handleScroll = () => {
      const { scrollTop, clientHeight, scrollHeight } = scrollElement;
      if (scrollHeight - scrollTop - clientHeight < 300) {
        if (hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      }
    };

    scrollElement.addEventListener('scroll', handleScroll);
    return () => scrollElement.removeEventListener('scroll', handleScroll);
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Clear selection on folder change
  useEffect(() => {
    setSelectedPhotoIds(new Set());
  }, [folderId]);

  const toggleSelection = (photoId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSelected = new Set(selectedPhotoIds);
    if (newSelected.has(photoId)) {
      newSelected.delete(photoId);
    } else {
      newSelected.add(photoId);
    }
    setSelectedPhotoIds(newSelected);
  };

  const handleMove = async (targetFolderId: string | null) => {
    if (selectedPhotoIds.size === 0) return;
    try {
      await moveMutation.mutateAsync({ 
        photoIds: Array.from(selectedPhotoIds), 
        targetFolderId 
      });
      setSelectedPhotoIds(new Set());
      toast.success(`Moved ${selectedPhotoIds.size} photos`);
    } catch {
      toast.error('Failed to move photos');
    }
  };

  const handleDelete = async () => {
    if (selectedPhotoIds.size === 0) return;
    if (!confirm(`Are you sure you want to delete ${selectedPhotoIds.size} photos?`)) return;
    
    try {
      await deleteMutation.mutateAsync(Array.from(selectedPhotoIds));
      setSelectedPhotoIds(new Set());
      toast.success(`Deleted ${selectedPhotoIds.size} photos`);
    } catch {
      toast.error('Failed to delete photos');
    }
  };

  const renderFolderMenu = (nodes: FolderNode[]) => {
    return nodes.map(node => (
      <React.Fragment key={node.id}>
        {node.children && node.children.length > 0 ? (
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <FolderOpen className="mr-2 h-4 w-4 text-muted-foreground" />
              <span className="truncate max-w-[120px]">{node.name}</span>
            </DropdownMenuSubTrigger>
            <DropdownMenuPortal>
              <DropdownMenuSubContent>
                <DropdownMenuItem onClick={() => handleMove(node.id)}>Move Here</DropdownMenuItem>
                <DropdownMenuSeparator />
                {renderFolderMenu(node.children)}
              </DropdownMenuSubContent>
            </DropdownMenuPortal>
          </DropdownMenuSub>
        ) : (
          <DropdownMenuItem onClick={() => handleMove(node.id)}>
            <FolderOpen className="mr-2 h-4 w-4 text-muted-foreground" />
            <span className="truncate max-w-[150px]">{node.name}</span>
          </DropdownMenuItem>
        )}
      </React.Fragment>
    ));
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (photos.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-center p-8 text-muted-foreground border-2 border-dashed rounded-lg mx-4 mt-4">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ImageIcon className="h-8 w-8" />
        </div>
        <h3 className="font-semibold text-foreground text-lg mb-1">No photos here</h3>
        <p className="text-sm max-w-sm mb-6">Upload photos to this folder or move them from another folder.</p>
        <Button>Upload Photos</Button>
      </div>
    );
  }

  const isSelectionMode = selectedPhotoIds.size > 0;

  return (
    <div className="relative h-full flex flex-col">
      <div 
        ref={parentRef} 
        className="flex-1 overflow-auto p-4"
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            return (
              <div
                key={virtualRow.index}
                className="absolute top-0 left-0 w-full grid gap-4"
                style={{
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                  gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                  paddingBottom: '16px'
                }}
              >
                {Array.from({ length: columns }).map((_, colIndex) => {
                  const photoIndex = virtualRow.index * columns + colIndex;
                  const photo = photos[photoIndex];
                  
                  if (!photo) return <div key={colIndex} />; // Empty cell

                  const isSelected = selectedPhotoIds.has(photo.id);

                  return (
                    <div 
                      key={photo.id}
                      className="group relative aspect-square bg-muted rounded-md overflow-hidden cursor-pointer shadow-sm border border-border/50"
                      onClick={() => isSelectionMode ? toggleSelection(photo.id, { stopPropagation: () => {} } as any) : onPhotoClick(photo)}
                    >
                      {photo.proxyUrl && (
                        <Image
                          src={photo.proxyUrl}
                          alt={photo.filename}
                          fill
                          className={cn(
                            "object-cover transition-transform duration-300",
                            isSelected ? "scale-95 brightness-90" : "group-hover:scale-105"
                          )}
                          sizes="(max-width: 768px) 50vw, (max-width: 1200px) 33vw, 25vw"
                          unoptimized // for picsum mocks
                        />
                      )}
                      
                      {/* Checkbox Overlay */}
                      <div 
                        className={cn(
                          "absolute top-2 left-2 z-10 transition-opacity",
                          isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                        )}
                        onClick={(e) => toggleSelection(photo.id, e)}
                      >
                        <div className={cn(
                          "bg-background/80 backdrop-blur-sm rounded p-0.5",
                          isSelected && "bg-primary text-primary-foreground"
                        )}>
                          <Checkbox checked={isSelected} className="pointer-events-none" />
                        </div>
                      </div>

                      {/* Face count badge */}
                      {photo.faceCount > 0 && (
                        <div className="absolute bottom-2 right-2 bg-black/60 backdrop-blur-md text-white text-[10px] font-medium px-1.5 py-0.5 rounded-full flex items-center gap-1">
                          👤 {photo.faceCount}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {isFetchingNextPage && (
          <div className="flex justify-center p-4">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>

      {/* Floating Action Toolbar */}
      {isSelectionMode && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 bg-foreground/95 backdrop-blur-lg text-background px-6 py-3 rounded-full shadow-2xl animate-in slide-in-from-bottom-5">
          <span className="font-semibold">{selectedPhotoIds.size} selected</span>
          
          <div className="h-5 w-px bg-background/20" />
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="text-background hover:bg-background/20 hover:text-background h-8 px-3">
                <Move className="mr-2 h-4 w-4" /> Move
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="center" className="w-56">
              <DropdownMenuItem onClick={() => handleMove(null)}>
                <FolderOpen className="mr-2 h-4 w-4 text-muted-foreground" />
                All Photos (Root)
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {renderFolderMenu(folders)}
            </DropdownMenuContent>
          </DropdownMenu>

          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleDelete}
            className="text-red-400 hover:bg-red-400/20 hover:text-red-400 h-8 px-3"
          >
            <Trash2 className="mr-2 h-4 w-4" /> Delete
          </Button>
          
          <div className="h-5 w-px bg-background/20" />
          
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => setSelectedPhotoIds(new Set())}
            className="text-background hover:bg-background/20 hover:text-background h-8 w-8 rounded-full"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
