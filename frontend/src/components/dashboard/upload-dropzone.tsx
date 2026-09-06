import React, { useCallback, useState } from 'react';
import { useDropzone, FileRejection } from 'react-dropzone';
import { UploadCloud, Folder as FolderIcon } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { FolderNode } from '@/types/event';
import { uploadManager } from '@/lib/upload/upload-manager';
import { isValidFileType } from '@/lib/upload/file-utils';

interface UploadDropzoneProps {
  eventId: string;
  folders: FolderNode[];
}

export function UploadDropzone({ eventId, folders }: UploadDropzoneProps) {
  const [targetFolderId, setTargetFolderId] = useState<string>('root');

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: FileRejection[]) => {
    if (fileRejections.length > 0) {
      toast.error(`Rejected ${fileRejections.length} files. Unsupported format.`);
    }

    const validFiles = acceptedFiles.filter(isValidFileType);
    if (validFiles.length === 0) return;

    // Extract path using webkitRelativePath if available, otherwise just use filename
    const items = validFiles.map(file => {
      // @ts-ignore
      const path = file.path || file.webkitRelativePath || file.name;
      // react-dropzone adds a path property. 
      // e.g. path = "/Folder/IMG.jpg", remove leading slash
      const cleanPath = path.startsWith('/') ? path.substring(1) : path;
      return { file, relativePath: cleanPath };
    });

    const rootId = targetFolderId === 'root' ? null : targetFolderId;
    
    // Add to upload manager queue (it handles API folder creation too)
    toast.promise(uploadManager.queueFiles(eventId, rootId, items), {
      loading: 'Preparing files for upload...',
      success: `Queued ${validFiles.length} files for upload`,
      error: 'Failed to queue files',
    });
  }, [eventId, targetFolderId]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    noClick: true, // We want custom buttons instead of full area click
  });

  // Flatten folders for the select dropdown
  const renderFolderOptions = (nodes: FolderNode[], depth = 0): React.ReactNode[] => {
    let options: React.ReactNode[] = [];
    for (const node of nodes) {
      const prefix = '— '.repeat(depth);
      options.push(
        <SelectItem key={node.id} value={node.id}>
          {prefix}{node.name}
        </SelectItem>
      );
      if (node.children && node.children.length > 0) {
        options = options.concat(renderFolderOptions(node.children, depth + 1));
      }
    }
    return options;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <label className="text-sm font-medium whitespace-nowrap">Target Folder:</label>
        <Select value={targetFolderId} onValueChange={setTargetFolderId}>
          <SelectTrigger className="w-[300px]">
            <SelectValue placeholder="Select a folder" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="root">
              <span className="flex items-center">
                <FolderIcon className="mr-2 h-4 w-4" />
                All Photos (Root)
              </span>
            </SelectItem>
            {renderFolderOptions(folders)}
          </SelectContent>
        </Select>
      </div>

      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-xl p-12 text-center transition-colors bg-muted/20",
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"
        )}
      >
        <input {...getInputProps()} />
        
        <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-6">
          <UploadCloud className="h-8 w-8 text-primary" />
        </div>
        
        <h3 className="text-xl font-semibold mb-2">Drag & drop files or folders here</h3>
        <p className="text-muted-foreground mb-8">
          Supports: JPG, PNG, HEIC, TIFF, WebP (Max 50MB per file)
        </p>

        <div className="flex justify-center gap-4">
          {/* We use two hidden inputs for file vs folder selection */}
          <Button variant="outline" asChild>
            <label className="cursor-pointer">
              Browse Files
              <input 
                type="file" 
                multiple 
                className="hidden" 
                onChange={(e) => {
                  if (e.target.files) onDrop(Array.from(e.target.files), []);
                  e.target.value = ''; // reset
                }}
                accept="image/jpeg,image/png,image/webp,image/heic,image/tiff"
              />
            </label>
          </Button>
          <Button variant="outline" asChild>
            <label className="cursor-pointer">
              Browse Folder
              <input 
                type="file" 
                // @ts-ignore - webkitdirectory is non-standard but widely supported
                webkitdirectory="" 
                directory="" 
                multiple
                className="hidden" 
                onChange={(e) => {
                  if (e.target.files) onDrop(Array.from(e.target.files), []);
                  e.target.value = ''; // reset
                }}
              />
            </label>
          </Button>
        </div>
      </div>
    </div>
  );
}
