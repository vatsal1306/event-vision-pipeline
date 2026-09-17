import { describe, it, expect } from 'vitest';
import { FolderNode } from '@/types/event';
import { collectFolderPhotoCounts } from '@/lib/folder-tree';
import {
  getOffsetNextPageParam,
  getPaginatedTotal,
  shouldFetchNextPage,
  shouldShowPaginatedEmptyState,
} from '@/lib/pagination';

describe('getOffsetNextPageParam', () => {
  it('should return the next offset while items remain', () => {
    expect(getOffsetNextPageParam({ offset: 0, limit: 50, total: 1000 })).toBe(50);
    expect(getOffsetNextPageParam({ offset: 50, limit: 50, total: 1000 })).toBe(100);
  });

  it('should stop at the last partial page', () => {
    expect(getOffsetNextPageParam({ offset: 950, limit: 50, total: 1000 })).toBeUndefined();
  });

  it('should stop when total is zero or fits in the first page', () => {
    expect(getOffsetNextPageParam({ offset: 0, limit: 50, total: 0 })).toBeUndefined();
    expect(getOffsetNextPageParam({ offset: 0, limit: 50, total: 50 })).toBeUndefined();
    expect(getOffsetNextPageParam({ offset: 0, limit: 50, total: 12 })).toBeUndefined();
  });
});

describe('getPaginatedTotal', () => {
  it('should read total from the first infinite-query page', () => {
    expect(getPaginatedTotal([{ total: 240 }, { total: 240 }], 50)).toBe(240);
  });

  it('should fall back to loaded count before any page arrives', () => {
    expect(getPaginatedTotal(undefined, 0)).toBe(0);
    expect(getPaginatedTotal([], 12)).toBe(12);
  });
});

describe('shouldShowPaginatedEmptyState', () => {
  it('should hide empty state while more pages can still load', () => {
    expect(
      shouldShowPaginatedEmptyState({ loadedCount: 0, hasMore: true, isLoadingMore: false })
    ).toBe(false);
  });

  it('should hide empty state while a next page is in flight', () => {
    expect(
      shouldShowPaginatedEmptyState({ loadedCount: 0, hasMore: false, isLoadingMore: true })
    ).toBe(false);
  });

  it('should show empty state only after pages are exhausted with no items', () => {
    expect(
      shouldShowPaginatedEmptyState({ loadedCount: 0, hasMore: false, isLoadingMore: false })
    ).toBe(true);
  });

  it('should not show empty state when items are already loaded', () => {
    expect(
      shouldShowPaginatedEmptyState({ loadedCount: 3, hasMore: false, isLoadingMore: false })
    ).toBe(false);
  });
});

describe('shouldFetchNextPage', () => {
  it('should fetch when the sentinel is within the threshold', () => {
    expect(
      shouldFetchNextPage({
        hasMore: true,
        isLoadingMore: false,
        distanceFromBottomPx: 400,
        thresholdPx: 600,
      })
    ).toBe(true);
  });

  it('should not fetch while a page is already loading', () => {
    expect(
      shouldFetchNextPage({
        hasMore: true,
        isLoadingMore: true,
        distanceFromBottomPx: 0,
        thresholdPx: 600,
      })
    ).toBe(false);
  });

  it('should not fetch when pages are exhausted or the user is still far from the bottom', () => {
    expect(
      shouldFetchNextPage({
        hasMore: false,
        isLoadingMore: false,
        distanceFromBottomPx: 0,
        thresholdPx: 600,
      })
    ).toBe(false);
    expect(
      shouldFetchNextPage({
        hasMore: true,
        isLoadingMore: false,
        distanceFromBottomPx: 900,
        thresholdPx: 600,
      })
    ).toBe(false);
  });
});

describe('collectFolderPhotoCounts', () => {
  it('should walk nested folders and keep backend photo_count values', () => {
    const folders: FolderNode[] = [
      {
        id: 'ceremony',
        eventId: 'evt',
        parentId: null,
        name: 'Ceremony',
        sortOrder: 0,
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
        photoCount: 120,
        children: [
          {
            id: 'vows',
            eventId: 'evt',
            parentId: 'ceremony',
            name: 'Vows',
            sortOrder: 0,
            createdAt: '2026-01-01T00:00:00Z',
            updatedAt: '2026-01-01T00:00:00Z',
            photoCount: 40,
            children: [],
          },
        ],
      },
    ];

    expect(collectFolderPhotoCounts(folders)).toEqual({ ceremony: 120, vows: 40 });
  });
});
