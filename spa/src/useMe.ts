import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import type { Me } from "./api/types";

export interface MeState {
  me: Me | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useMe(): MeState {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getMe()
      .then((data) => {
        if (!cancelled) {
          setMe(data);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e.message || e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  return { me, loading, error, reload };
}
