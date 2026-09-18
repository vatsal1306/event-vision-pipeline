import { useEffect, useRef } from 'react';

interface UsePrefetchNextPageOptions {
  hasNextPage: boolean | undefined;
  isFetchingNextPage: boolean;
  pageCount: number;
  fetchNextPage: () => void;
  enabled?: boolean;
}

/**
 * Warms the next gallery page into the query cache as soon as the current
 * page settles, instead of waiting for the user to scroll near the bottom.
 *
 * Reuses the infinite query's own `fetchNextPage` (rather than a separate
 * `queryClient.prefetchInfiniteQuery` call) so it appends exactly one page to
 * the existing cache. `prefetchInfiniteQuery` re-fetches every already-loaded
 * page from scratch whenever the query's `staleTime` is 0 (as the guest
 * gallery hooks use), which would double the network cost instead of saving
 * it — `fetchNextPage` always appends a single page, regardless of staleTime.
 *
 * Capped to exactly one page ahead: fires once per page-count change, never
 * stacks further fetches while one is already in flight.
 */
export function usePrefetchNextPage(options: UsePrefetchNextPageOptions) {
  const { hasNextPage, isFetchingNextPage, pageCount, fetchNextPage, enabled = true } = options;
  const prefetchedForPageCount = useRef(-1);

  useEffect(() => {
    if (!enabled || !hasNextPage || isFetchingNextPage || pageCount === 0) {
      return;
    }
    if (prefetchedForPageCount.current === pageCount) {
      return;
    }
    prefetchedForPageCount.current = pageCount;
    fetchNextPage();
  }, [enabled, hasNextPage, isFetchingNextPage, pageCount, fetchNextPage]);
}
