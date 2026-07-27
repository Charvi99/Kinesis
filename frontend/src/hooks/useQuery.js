import { useCallback, useEffect, useRef, useState } from 'react';

// Async-data hook (from frontend-patterns): stable refetch, no inline-fn fetch loop.
export function useQuery(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  useEffect(() => { fetcherRef.current = fetcher; });

  const refetch = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await fetcherRef.current()); }
    catch (e) { setError(e.response?.data?.detail || e.message || 'Request failed'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refetch(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, deps);
  return { data, error, loading, refetch };
}
