type SynchronizationProps = {
  error: string;
  syncedAt?: Date;
  automatic?: boolean;
};

export function Synchronization({ error, syncedAt, automatic = true }: SynchronizationProps) {
  return <p className="sync-status" role={error ? "alert" : "status"}>
    {error ? "Atualização indisponível: " + error + " Os dados exibidos podem estar desatualizados. "
      : automatic ? "Atualização automática a cada 3 segundos. " : "Histórico atualizado sob demanda. "}
    {syncedAt && "Última sincronização: " + syncedAt.toLocaleTimeString("pt-BR") + "."}
  </p>;
}
