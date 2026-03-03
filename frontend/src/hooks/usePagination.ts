import { useState, useCallback } from 'react';
import type { CursorPage } from '../lib/types';

export function usePagination<T>(
  fetcher: (cursor?: string) => Promise<unknown>,
) {
  const [items, setItems] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (reset = false) => {
    setLoading(true);
    try {
      const page = (await fetcher(reset ? undefined : (cursor ?? undefined))) as CursorPage<T>;
      setItems((prev) => (reset ? page.items : [...prev, ...page.items]));
      setCursor(page.next_cursor);
      setHasMore(page.has_more);
    } finally {
      setLoading(false);
    }
  }, [fetcher, cursor]);

  const loadMore = useCallback(() => {
    if (hasMore && !loading) load();
  }, [hasMore, loading, load]);

  const refresh = useCallback(() => load(true), [load]);

  return { items, hasMore, loading, loadMore, refresh };
}
