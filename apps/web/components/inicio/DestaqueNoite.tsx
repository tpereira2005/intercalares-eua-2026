import Link from "next/link";
import type { ReactNode } from "react";
import { Probabilidade } from "@/components/resultados/PainelProjecao.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { formatarHora, formatarNumero } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CamaraNoite, VistaNoite } from "@/lib/noite/vista.ts";

/** Destaque da página inicial na noite eleitoral; nunca com um ensaio. */
export function DestaqueNoite({
  noite,
  ligacao = null,
  depois = false,
}: {
  noite: VistaNoite;
  /** Nos dias da contagem lenta, depois da noite. */
  depois?: boolean;
  /** Estado da ligação à API, quando o destaque se atualiza no browser. */
  ligacao?: ReactNode;
}) {
  if (noite.ensaio) return null;
  const linha = (r: CamaraNoite) => {
    const lider = r.probD >= r.probR ? "D" : "R";
    return (
      <div className="flex flex-col gap-1">
        <dt className="rotulo">{t(`noite.inicio.${r.camara}`)}</dt>
        <dd className="text-[22px]">
          <Probabilidade lado={lider} valor={lider === "D" ? r.probD : r.probR} />
        </dd>
        <dd className="font-mono text-[12px] text-ink-3">
          {t("noite.camara.lugares", {
            mediana: r.mediana,
            de: r.p10,
            ate: r.p90,
            maioria: r.maioria,
            corridas: r.corridasComVotos,
          })}
        </dd>
      </div>
    );
  };
  return (
    <Painel
      sobrelinha={t(depois ? "noite.inicio.sobrelinhaDepois" : "noite.inicio.sobrelinha")}
      titulo={t("noite.inicio.titulo")}
      descricao={t("noite.sobrelinha", { hora: formatarHora(new Date(noite.instante)) })}
      acessorio={
        <span className="flex flex-wrap gap-1.5">
          <Selo variante="sinal">{t("comum.selos.aoVivo")}</Selo>
          <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>
        </span>
      }
      fontes={noite.fontes}
      metodo={t("noite.metodo", { simulacoes: formatarNumero(noite.simulacoes) })}
    >
      <dl className="grid gap-4 sm:grid-cols-2">
        {linha(noite.camara)}
        {linha(noite.senado)}
      </dl>
      <p className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Link
          href="/resultados/"
          className="text-ink underline decoration-rule underline-offset-[3px]"
        >
          {t("noite.inicio.ligacao")}
        </Link>
        {ligacao}
      </p>
    </Painel>
  );
}
