import { Clock } from 'lucide-react';
import { EmptyState } from '@/components/shared/empty-state';

interface GalleryNotReadyProps {
  eventName?: string;
}

/**
 * Guest and couple empty state when the photographer has not finished face matching.
 */
export function GalleryNotReady({ eventName }: GalleryNotReadyProps) {
  const description = eventName
    ? `${eventName} is still being prepared. Your photographer will share this gallery when face matching is done.`
    : 'This gallery is still being prepared. Check back after your photographer finishes finding faces.';

  return (
    <div className="flex min-h-screen items-center justify-center bg-black p-4">
      <EmptyState
        title="Photos aren't ready yet"
        description={description}
        icon={<Clock className="h-10 w-10 text-zinc-500" />}
        variant="dark"
      />
    </div>
  );
}
