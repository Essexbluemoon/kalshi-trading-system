/**
 * useApi.js
 * Shared data-fetching hook. Wraps fetch against the FastAPI backend.
 * Handles auth header, loading state, and error state.
 * Implemented in Phase 5.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useApi("/positions");
 */
import { useCallback, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "";
const API_KEY  = import.meta.env.VITE_API_KEY  || "";

export function useApi(path, options = {}) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: {
          Authorization: `Bearer ${API_KEY}`,
          "Content-Type": "application/json",
          ...options.headers,
        },
        ...options,
      });
      if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);
      setData(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [path]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
