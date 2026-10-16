import { Selo } from "@/components/ui/Selo.tsx";
import { formatarDataHora } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { Atraso } from "@/lib/resultados/atrasos.ts";

/** Frase sobre uma fonte atrasada: o motivo e a hora dos últimos dados novos. */
export function textoAtraso(atraso: Atraso): string {
  if (atraso.desde) {
    return t(`resultados.cobertura.atraso.${atraso.motivo}`, {
      hora: formatarDataHora(new Date(atraso.desde)),
    });
  }
  return t(`resultados.cobertura.atraso.${atraso.motivo}SemHora`);
}

/** Selo «Fonte atrasada» e a frase, para a cobertura e para a página da corrida. */
export function AvisoAtraso({ atraso }: { atraso: Atraso }) {
  return (
    <span className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[12.5px] text-ink-2">
      <Selo>{t("resultados.cobertura.atraso.selo")}</Selo>
      <span>{textoAtraso(atraso)}</span>
    </span>
  );
}
