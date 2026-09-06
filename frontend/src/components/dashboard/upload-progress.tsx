import React, { useEffect, useState } from 'react';
import { useUploadStore } from '@/stores/upload-store';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { CheckCircle2, AlertCircle, Pause, Play, X, Loader2 } from 'lucide-react';
import { formatTime, formatSpeed } from '@/lib/upload/file-utils';
import { cn } from '@/lib/utils';
import { uploadManager } from '@/lib/upload/upload-manager';

interface UploadProgressProps {
  eventId: string;
}

export function UploadProgress({ eventId }: UploadProgressProps) {
  const store = useUploadStore();
  const evState = store.events[eventId];

  const [lastBytes, setLastBytes] = useState(evState?.uploadedBytes || 0);
  const [speed, setSpeed] = useState(0);

  // Speed calculation
  useEffect(() => {
    if (!evState || evState.status !== 'uploading') {
      setSpeed(0);
      return;
    }

    const interval = setInterval(() => {
      const currentBytes = useUploadStore.getState().events[eventId]?.uploadedBytes || 0;
      setSpeed(Math.max(0, currentBytes - lastBytes));
      setLastBytes(currentBytes);
    }, 1000);

    return () => clearInterval(interval);
  }, [evState?.status, lastBytes, eventId]);

  if (!evState || evState.files.length === 0) {
    return null;
  }

  const overallProgress = evState.totalBytes > 0 ? (evState.uploadedBytes / evState.totalBytes) * 100 : 0;
  const remainingBytes = evState.totalBytes - evState.uploadedBytes;
  const eta = speed > 0 ? remainingBytes / speed : 0;

  const handlePauseResumeAll = () => {
    if (evState.status === 'paused') {
      store.resumeEvent(eventId);
    } else {
      store.pauseEvent(eventId);
    }
  };

  const handleCancelAll = () => {
    if (confirm('Are you sure you want to cancel all uploads?')) {
      store.cancelEvent(eventId);
    }
  };

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold border-b-2 border-primary pb-1 inline-block">Upload Progress</h3>
        
        <div className="flex gap-2">
          {evState.status !== 'complete' && evState.files.length > 0 && (
            <>
              <Button variant="outline" size="sm" onClick={handlePauseResumeAll}>
                {evState.status === 'paused' ? (
                  <><Play className="mr-2 h-4 w-4" /> Resume All</>
                ) : (
                  <><Pause className="mr-2 h-4 w-4" /> Pause All</>
                )}
              </Button>
              <Button variant="outline" size="sm" onClick={handleCancelAll} className="text-destructive">
                <X className="mr-2 h-4 w-4" /> Cancel All
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="bg-card border rounded-xl p-6 shadow-sm mb-6">
        <div className="flex justify-between text-sm mb-2 font-medium">
          <span>Overall Progress: {Math.round(overallProgress)}%</span>
          <span>{evState.completedFiles} / {evState.totalFiles} Files</span>
        </div>
        <Progress value={overallProgress} className="h-2 mb-3" />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{formatSpeed(speed)}</span>
          <span>ETA: {evState.status === 'uploading' ? formatTime(eta) : '--'}</span>
        </div>
      </div>

      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
        {evState.files.map((file) => {
          const fileProgress = (file.uploadedBytes / file.totalBytes) * 100;
          
          return (
            <div key={file.id} className="flex items-center gap-4 bg-muted/30 p-3 rounded-lg border">
              <div className="flex-1 min-w-0">
                <div className="flex justify-between mb-1">
                  <span className="text-sm font-medium truncate pr-4">{file.relativePath || file.file?.name || 'Unknown file'}</span>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {(file.totalBytes / (1024 * 1024)).toFixed(1)} MB
                  </span>
                </div>
                <Progress 
                  value={fileProgress} 
                  className={cn(
                    "h-1.5", 
                    file.status === 'failed' && "bg-destructive/20 [&>div]:bg-destructive"
                  )} 
                />
              </div>

              <div className="w-24 flex items-center justify-end flex-shrink-0">
                {file.status === 'complete' && (
                  <span className="text-green-500 flex items-center text-sm font-medium">
                    <CheckCircle2 className="h-4 w-4 mr-1" /> Done
                  </span>
                )}
                {file.status === 'uploading' && (
                  <span className="text-primary flex items-center text-sm font-medium">
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" /> {Math.round(fileProgress)}%
                  </span>
                )}
                {file.status === 'queued' && (
                  <span className="text-muted-foreground text-sm">Queued</span>
                )}
                {file.status === 'failed' && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive h-8 px-2"
                    onClick={() => store.retryFile(eventId, file.id)}
                  >
                    <AlertCircle className="h-4 w-4 mr-1" /> Retry
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
