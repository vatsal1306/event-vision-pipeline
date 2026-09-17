import { FolderNode } from '@/types/event';

/**
 * Flatten a folder tree into id → photo_count from the API.
 *
 * Counts come from the backend folder payload, not from currently loaded photo pages.
 */
export function collectFolderPhotoCounts(folders: FolderNode[]): Record<string, number> {
  const counts: Record<string, number> = {};

  const walk = (nodes: FolderNode[]): void => {
    for (const node of nodes) {
      if (typeof node.photoCount === 'number') {
        counts[node.id] = node.photoCount;
      }
      if (node.children.length > 0) {
        walk(node.children);
      }
    }
  };

  walk(folders);
  return counts;
}
