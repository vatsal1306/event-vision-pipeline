'use client';

import { Folder } from '@/types/event';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface FolderNavProps {
  folders: Folder[];
  selectedFolderId: string | null;
  onSelectFolder: (id: string | null) => void;
  className?: string;
}

export function FolderNav({
  folders,
  selectedFolderId,
  onSelectFolder,
  className,
}: FolderNavProps) {
  return (
    <div className={cn('w-full overflow-x-auto no-scrollbar py-2', className)}>
      <div className="flex gap-2 min-w-max px-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onSelectFolder(null)}
          className={cn(
            'rounded-pill border-muted bg-transparent hover:bg-muted text-muted-foreground',
            selectedFolderId === null && 'bg-primary text-primary-foreground border-primary hover:bg-primary hover:text-primary-foreground'
          )}
        >
          All Photos
        </Button>
        
        {folders.map((folder) => (
          <Button
            key={folder.id}
            variant="outline"
            size="sm"
            onClick={() => onSelectFolder(folder.id)}
            className={cn(
              'rounded-pill border-muted bg-transparent hover:bg-muted text-muted-foreground',
              selectedFolderId === folder.id && 'bg-primary text-primary-foreground border-primary hover:bg-primary hover:text-primary-foreground'
            )}
          >
            {folder.name}
          </Button>
        ))}
      </div>
    </div>
  );
}
