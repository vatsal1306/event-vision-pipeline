import { useState } from 'react';
import { FolderNode } from '@/types/event';
import { useCreateFolder, useRenameFolder, useDeleteFolder } from '@/hooks/use-folders';
import { FolderOpen, ChevronRight, ChevronDown, MoreHorizontal, Plus, Trash2, Edit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface FolderTreeProps {
  eventId: string;
  folders: FolderNode[];
  activeFolderId: string | null;
  onFolderSelect: (folderId: string | null) => void;
  isLoading?: boolean;
}

export function FolderTree({ eventId, folders, activeFolderId, onFolderSelect, isLoading }: FolderTreeProps) {
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [creatingParentId, setCreatingParentId] = useState<string | null | undefined>(undefined);
  const [newFolderName, setNewFolderName] = useState('');
  const [renamingFolderId, setRenamingFolderId] = useState<string | null>(null);

  const createFolderMutation = useCreateFolder(eventId);
  const renameFolderMutation = useRenameFolder(eventId);
  const deleteFolderMutation = useDeleteFolder(eventId);

  const toggleFolder = (folderId: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(folderId)) {
      newExpanded.delete(folderId);
    } else {
      newExpanded.add(folderId);
    }
    setExpandedFolders(newExpanded);
  };

  const handleCreateSubmit = async (e: React.FormEvent, parentId: string | null) => {
    e.preventDefault();
    if (!newFolderName.trim()) {
      setCreatingParentId(undefined);
      return;
    }
    try {
      await createFolderMutation.mutateAsync({ name: newFolderName, parentId });
      setCreatingParentId(undefined);
      setNewFolderName('');
      toast.success('Folder created');
    } catch {
      toast.error('Failed to create folder');
    }
  };

  const handleRenameSubmit = async (e: React.FormEvent, folderId: string) => {
    e.preventDefault();
    if (!newFolderName.trim()) {
      setRenamingFolderId(null);
      return;
    }
    try {
      await renameFolderMutation.mutateAsync({ folderId, name: newFolderName });
      setRenamingFolderId(null);
      setNewFolderName('');
      toast.success('Folder renamed');
    } catch {
      toast.error('Failed to rename folder');
    }
  };

  const handleDelete = async (folderId: string) => {
    if (!confirm('Are you sure you want to delete this folder?')) return;
    try {
      await deleteFolderMutation.mutateAsync(folderId);
      if (activeFolderId === folderId) {
        onFolderSelect(null);
      }
      toast.success('Folder deleted');
    } catch {
      toast.error('Failed to delete folder');
    }
  };

  const renderNode = (node: FolderNode, level: number = 0) => {
    const isExpanded = expandedFolders.has(node.id);
    const isActive = activeFolderId === node.id;
    const isRenaming = renamingFolderId === node.id;
    const isCreatingChild = creatingParentId === node.id;

    return (
      <div key={node.id}>
        <div
          className={cn(
            'group flex items-center justify-between rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
            isActive && 'bg-accent text-accent-foreground',
            level > 0 && `ml-${level * 4}`
          )}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
        >
          <div className="flex flex-1 items-center gap-2 overflow-hidden cursor-pointer" onClick={() => onFolderSelect(node.id)}>
            {node.children && node.children.length > 0 ? (
              <button
                onClick={(e) => { e.stopPropagation(); toggleFolder(node.id); }}
                className="h-4 w-4 shrink-0 text-muted-foreground"
              >
                {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
            ) : (
              <span className="w-4" />
            )}
            <FolderOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
            {isRenaming ? (
              <form onSubmit={(e) => handleRenameSubmit(e, node.id)} className="flex-1" onClick={e => e.stopPropagation()}>
                <Input
                  autoFocus
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onBlur={() => setRenamingFolderId(null)}
                  className="h-7 py-1 px-2 text-xs"
                />
              </form>
            ) : (
              <span className="truncate">{node.name}</span>
            )}
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">More</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => {
                setNewFolderName('');
                setCreatingParentId(node.id);
                setExpandedFolders(prev => new Set(prev).add(node.id));
              }}>
                <Plus className="mr-2 h-4 w-4" /> Create subfolder
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => {
                setNewFolderName(node.name);
                setRenamingFolderId(node.id);
              }}>
                <Edit2 className="mr-2 h-4 w-4" /> Rename
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleDelete(node.id)} className="text-destructive focus:text-destructive">
                <Trash2 className="mr-2 h-4 w-4" /> Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {isExpanded && node.children && node.children.length > 0 && (
          <div>{node.children.map(child => renderNode(child, level + 1))}</div>
        )}

        {isCreatingChild && (
          <div className="flex items-center gap-2 px-2 py-1.5" style={{ paddingLeft: `${(level + 1) * 16 + 8}px` }}>
            <FolderOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
            <form onSubmit={(e) => handleCreateSubmit(e, node.id)} className="flex-1">
              <Input
                autoFocus
                placeholder="Folder name..."
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onBlur={() => setCreatingParentId(undefined)}
                className="h-7 py-1 px-2 text-xs"
              />
            </form>
          </div>
        )}
      </div>
    );
  };

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground animate-pulse">Loading folders...</div>;
  }

  const isCreatingRoot = creatingParentId === null;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h3 className="font-semibold text-sm">Folders</h3>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => {
            setNewFolderName('');
            setCreatingParentId(null);
          }}
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      
      <div className="flex-1 overflow-auto p-2">
        <div
          className={cn(
            'flex items-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground cursor-pointer mb-1',
            activeFolderId === null && 'bg-accent text-accent-foreground'
          )}
          onClick={() => onFolderSelect(null)}
        >
          <FolderOpen className="h-4 w-4 text-primary" />
          <span>All Photos</span>
        </div>

        <div className="space-y-0.5">
          {folders.map(folder => renderNode(folder))}
          
          {isCreatingRoot && (
            <div className="flex items-center gap-2 px-2 py-1.5 ml-2">
              <FolderOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
              <form onSubmit={(e) => handleCreateSubmit(e, null)} className="flex-1">
                <Input
                  autoFocus
                  placeholder="Folder name..."
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onBlur={() => setCreatingParentId(undefined)}
                  className="h-7 py-1 px-2 text-xs"
                />
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
