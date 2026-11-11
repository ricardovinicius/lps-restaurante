import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, type Configuration } from "../api";
import { usePolling } from "../hooks/usePolling";

type ConfigurationState = {
  configuration?: Configuration;
  error: string;
  failure: unknown;
  syncedAt?: Date;
  accept: (value: Configuration) => void;
  reload: () => Promise<Configuration>;
};

const Context = createContext<ConfigurationState | undefined>(undefined);

export function ConfigurationProvider({ children }: { children: ReactNode }) {
  const [configuration, setConfiguration] = useState<Configuration>();
  const newest = useRef<Configuration | undefined>(undefined);
  const pending = useRef<Promise<Configuration> | undefined>(undefined);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const accept = useCallback((value: Configuration) => {
    if (!mounted.current || (newest.current && value.revision <= newest.current.revision)) return;

    newest.current = value;
    setConfiguration(value);
  }, []);

  const read = useCallback(() => {
    if (!pending.current) {
      pending.current = api.configuration().then((value) => {
        accept(value);
        return newest.current ?? value;
      }).finally(() => { pending.current = undefined; });
    }
    return pending.current;
  }, [accept]);
  const sync = usePolling(read);
  const reload = useCallback(async () => {
    await pending.current?.catch(() => undefined);
    return read();
  }, [read]);

  return <Context.Provider value={{ configuration, accept, reload,
    error: sync.error, failure: sync.failure, syncedAt: sync.syncedAt }}>
    {children}
  </Context.Provider>;
}

export function useConfiguration() {
  const value = useContext(Context);
  if (!value) throw new Error("A configuração precisa estar dentro do seu provider.");
  return value;
}
