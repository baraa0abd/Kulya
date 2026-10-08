"use client";

import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";

export interface Loaded<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

function useLoad<T>(path: string | null, fetcher: (path: string) => Promise<T>): Loaded<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: path !== null,
  });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    fetcher(path).then(
      (data) => !cancelled && setState({ data, error: null, loading: false }),
      (error: unknown) =>
        !cancelled && setState({ data: null, error: describeError(error), loading: false }),
    );
    return () => {
      cancelled = true;
    };
  }, [path, version, fetcher]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, reload };
}

/** GET one object. Pass null to skip (for example while the user is still loading). */
export const useGet = <T>(path: string | null) => useLoad<T>(path, api.get<T>);
/** GET the first page of a list. */
export const useList = <T>(path: string | null) => useLoad<T[]>(path, api.list<T>);

/** Runs a write, tracks pending/error, and returns true on success. */
export function useAction() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (action: () => Promise<unknown>): Promise<boolean> => {
    setPending(true);
    setError(null);
    try {
      await action();
      return true;
    } catch (caught) {
      setError(describeError(caught));
      return false;
    } finally {
      setPending(false);
    }
  }, []);
  return { run, pending, error };
}
