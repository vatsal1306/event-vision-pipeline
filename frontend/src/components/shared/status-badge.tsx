import React from 'react';
import { EventStatus } from '@/types/event';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: EventStatus;
  progress?: number;
  className?: string;
}

export function StatusBadge({ status, progress, className }: StatusBadgeProps) {
  const variants = {
    ready: 'bg-primary/10 text-primary border-primary/20',
    processing: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-500 dark:border-amber-900/50',
    uploading: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-500 dark:border-blue-900/50',
    draft: 'bg-muted text-muted-foreground border-border',
    archived: 'bg-muted/50 text-muted-foreground/70 border-border/50',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
        variants[status] || variants.draft,
        className
      )}
    >
      {status === 'processing' && progress !== undefined ? (
        <>
          <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
          Processing {progress}%
        </>
      ) : (
        status.charAt(0).toUpperCase() + status.slice(1)
      )}
    </span>
  );
}
