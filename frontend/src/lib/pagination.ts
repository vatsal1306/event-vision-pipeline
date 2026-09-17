import { INFINITE_SCROLL_THRESHOLD_PX } from '@/lib/constants';
import { PaginatedResponse } from '@/types/api';

type OffsetPage = Pick<PaginatedResponse<unknown>, 'offset' | 'limit' | 'total'>;

/**
 * React Query `getNextPageParam` for offset/limit list responses.
 *
 * Returns the next offset when more items remain, otherwise `undefined`
 * so `hasNextPage` becomes false.
 */
export function getOffsetNextPageParam(lastPage: OffsetPage): number | undefined {
  const nextOffset = lastPage.offset + lastPage.limit;
  if (nextOffset < lastPage.total) {
    return nextOffset;
  }
  return undefined;
}

/**
 * Total item count from the first infinite-query page.
 *
 * Falls back to the number of items already loaded when no page has arrived yet.
 */
export function getPaginatedTotal(
  pages: Array<Pick<PaginatedResponse<unknown>, 'total'>> | undefined,
  fallbackLoadedCount = 0
): number {
  const total = pages?.[0]?.total;
  return typeof total === 'number' ? total : fallbackLoadedCount;
}

/**
 * Whether a paginated list should show a terminal empty state.
 *
 * Empty loaded results are not terminal while more pages exist or a fetch is in flight.
 */
export function shouldShowPaginatedEmptyState(options: {
  loadedCount: number;
  hasMore: boolean;
  isLoadingMore?: boolean;
}): boolean {
  return options.loadedCount === 0 && !options.hasMore && !options.isLoadingMore;
}

/**
 * Whether scroll proximity should request the next page.
 */
export function shouldFetchNextPage(options: {
  hasMore: boolean;
  isLoadingMore: boolean;
  distanceFromBottomPx: number;
  thresholdPx?: number;
}): boolean {
  const thresholdPx = options.thresholdPx ?? INFINITE_SCROLL_THRESHOLD_PX;
  return options.hasMore && !options.isLoadingMore && options.distanceFromBottomPx <= thresholdPx;
}
