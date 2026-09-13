import React from 'react';
import { Event, EventStatus } from '@/types/event';
import { cn } from '@/lib/utils';
import { EventStatusTone, getEventStatusPresentation } from '@/lib/event-status';

interface StatusBadgeProps {
  status: EventStatus;
  event?: Pick<Event, 'status' | 'totalPhotos' | 'processedPhotos' | 'pendingFacePhotos'>;
  progress?: number;
  className?: string;
}

const toneClasses: Record<EventStatusTone, string> = {
  success:
    'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-900/50',
  warning:
    'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-500 dark:border-amber-900/50',
  info: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-500 dark:border-blue-900/50',
  muted: 'bg-muted/50 text-muted-foreground/70 border-border/50',
  neutral: 'bg-muted text-muted-foreground border-border',
};

export function StatusBadge({ status, event, progress, className }: StatusBadgeProps) {
  const presentation = getEventStatusPresentation(
    event ?? {
      status,
      totalPhotos: 0,
      processedPhotos: 0,
      pendingFacePhotos: 0,
    }
  );

  const showProcessingPercent =
    status === 'processing' && progress !== undefined && Number.isFinite(progress);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
        toneClasses[presentation.tone],
        className
      )}
    >
      {showProcessingPercent ? (
        <>
          <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
          {presentation.label} {progress}%
        </>
      ) : (
        <>
          {presentation.tone === 'success' || status === 'processing' ? (
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full bg-current',
                status === 'processing' && 'animate-pulse'
              )}
            />
          ) : null}
          {presentation.label}
        </>
      )}
    </span>
  );
}
