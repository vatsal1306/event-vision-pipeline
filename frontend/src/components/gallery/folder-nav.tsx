'use client';

import { FolderNode } from '@/types/event';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface FolderNavProps {
  folders: FolderNode[];
  selectedFolderId: string | null;
  onSelectFolder: (id: string | null) => void;
  photoCounts?: Record<string, number>;
  totalCount?: number;
  className?: string;
}

export function FolderNav({
  folders,
  selectedFolderId,
  onSelectFolder,
  photoCounts,
  totalCount,
  className,
}: FolderNavProps) {
  // Flatten folder tree
  const flattenedFolders: { id: string; name: string }[] = [];
  
  const flatten = (nodes: FolderNode[], parentPath = '') => {
    for (const node of nodes) {
      const currentPath = parentPath ? `${parentPath} > ${node.name}` : node.name;
      flattenedFolders.push({ id: node.id, name: currentPath });
      if (node.children && node.children.length > 0) {
        flatten(node.children, currentPath);
      }
    }
  };
  
  flatten(folders);
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
          All Photos {totalCount !== undefined ? `(${totalCount})` : ''}
        </Button>
        
        {flattenedFolders.map((folder) => (
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
            {folder.name} {photoCounts?.[folder.id] !== undefined ? `(${photoCounts[folder.id]})` : ''}
          </Button>
        ))}
      </div>
    </div>
  );
}
