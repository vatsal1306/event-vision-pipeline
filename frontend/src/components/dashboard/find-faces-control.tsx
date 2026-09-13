'use client';

import { ScanFace } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useStartFaceProcessing } from '@/hooks/use-face-processing';
import { shouldShowFindFacesButton } from '@/lib/face-processing';
import { Event } from '@/types/event';

interface FindFacesControlProps {
  event: Event;
}

/**
 * Photographer CTA to start face matching. Status is shown on the event badge,
 * not a progress bar (bulk percent is not reliable yet).
 */
export function FindFacesControl({ event }: FindFacesControlProps) {
  const startMutation = useStartFaceProcessing(event.id);
  const isProcessing = event.status === 'processing' || startMutation.isPending;
  const showButton = shouldShowFindFacesButton(event) && !isProcessing;

  return (
    <div className="flex min-w-0 flex-col items-stretch gap-3 sm:items-end">
      {showButton ? (
        <div className="flex flex-col items-end gap-1">
          <Button
            type="button"
            onClick={() => startMutation.mutate()}
            disabled={startMutation.isPending}
            className="bg-signal text-white hover:bg-signal/90"
          >
            <ScanFace />
            {startMutation.isPending ? 'Starting…' : 'Find faces'}
          </Button>
          <p className="max-w-xs text-right text-xs text-muted-foreground">
            When uploads are done, we group people so guests can find themselves.
          </p>
        </div>
      ) : null}

      {isProcessing ? (
        <p className="max-w-xs text-right text-xs font-medium text-signal">
          Finding faces in your photos. This can take a few minutes on larger events.
        </p>
      ) : null}
    </div>
  );
}
