import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api";

export function usePolling<T>(read: () => Promise<T>, interval: number | null = 3000, refreshKey?: number) {
  const [value, setValue] = useState<T>();
  const [error, setError] = useState("");
  const [failure, setFailure] = useState<unknown>();
  const [syncedAt, setSyncedAt] = useState<Date>();
  const [attempt, retry] = useState(0);
  const inFlight = useRef<Promise<T> | undefined>(undefined);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      if (inFlight.current) {
        await inFlight.current.catch(() => undefined);
      }
      if (!active) return;

      const pending = Promise.resolve().then(read);
      inFlight.current = pending;

      try {
        const result = await pending;
        if (active) {
          setValue(result);
          setError("");
          setFailure(undefined);
          setSyncedAt(new Date());
        }
      } catch (error) {
        if (active) {
          setError(errorMessage(error));
          setFailure(error);
        }
      } finally {
        if (inFlight.current === pending) inFlight.current = undefined;
        if (active && interval !== null) timer = setTimeout(poll, interval);
      }
    }

    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [read, attempt, interval, refreshKey]);

  const refresh = useCallback(() => retry((value) => value + 1), []);

  return { value, error, failure, syncedAt, refresh };
}
