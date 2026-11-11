import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api";

export function usePolling<T>(read: () => Promise<T>, interval: number | null = 3000, refreshKey?: number) {
  const [value, setValue] = useState<T>();
  const [error, setError] = useState("");
  const [syncedAt, setSyncedAt] = useState<Date>();
  const [attempt, retry] = useState(0);
  const inFlight = useRef(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      if (inFlight.current) {
        timer = setTimeout(poll, 3000);
        return;
      }
      inFlight.current = true;

      try {
        const result = await read();
        if (active) {
          setValue(result);
          setError("");
          setSyncedAt(new Date());
        }
      } catch (error) {
        if (active) setError(errorMessage(error));
      } finally {
        inFlight.current = false;
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

  return { value, error, syncedAt, refresh };
}

