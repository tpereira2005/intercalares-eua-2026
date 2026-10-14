import Link from "next/link";
import { BarraControlo, Estimativa } from "@/components/previsao/PaginaPrevisao.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { formatarData, formatarNumero } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { Camara, VistaPrevisao } from "@/lib/previsao/vista.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px] hover:decoration-ink-3";

function Linha({ vista, camara }: { vista: VistaPrevisao; camara: Camara }) {
  const r = vista[camara];
  return (
    <div className="flex flex-col gap-1.5">
      <h3 className="rotulo">{t(`inicio.previsao.${camara}`)}</h3>
      <BarraControlo resumo={r} />
      <p className="font-mono text-[12px] text-ink-3">
        {t("inicio.previsao.lugares", {
          mediana: r.mediana,
          de: r.p10,
          ate: r.p90,
          maioria: r.maioria,
        })}
      </p>
    </div>
  );
}

/**
 * Previsão da Câmara e do Senado na página inicial: probabilidade de controlo e lugares
 * democratas. Depois da noite, é a mesma previsão, lida como a que foi congelada.
 */
export function ResumoPrevisao({
  vista,
  depois = false,
}: {
  vista: VistaPrevisao | null;
  depois?: boolean;
}) {
  if (!vista) {
    return (
      <Painel
        sobrelinha={t("inicio.previsao.sobrelinha")}
        titulo={t("inicio.previsao.titulo")}
        acessorio={<Selo variante="tracejado">{t("comum.emPreparacao")}</Selo>}
      >
        <p className="max-w-[62ch] text-ink-2">{t("inicio.previsao.texto")}</p>
        <p className="text-sm">
          <Link href="/previsao/" className={LIGACAO}>
            {t("inicio.previsao.ligacao")}
          </Link>
        </p>
      </Painel>
    );
  }
  const corte = formatarData(new Date(`${vista.corte}T12:00:00Z`));
  return (
    <Painel
      sobrelinha={t(depois ? "inicio.previsao.sobrelinhaDepois" : "inicio.previsao.sobrelinha")}
      titulo={t("inicio.previsao.titulo")}
      descricao={t(vista.congelada ? "inicio.previsao.congelada" : "inicio.previsao.diaria", {
        data: corte,
        simulacoes: formatarNumero(vista.simulacoes),
      })}
      acessorio={
        <span className="flex flex-wrap gap-1.5">
          {vista.congelada ? (
            <Selo variante="solido">{t("previsao.selos.congelada")}</Selo>
          ) : (
            <Selo variante="sinal">{t("previsao.selos.diaria")}</Selo>
          )}
          <Estimativa />
        </span>
      }
      fontes={[{ nome: t("inicio.previsao.fonte"), url: "/previsao/" }]}
      metodo={t("inicio.previsao.metodo")}
    >
      <div className="grid gap-4 sm:grid-cols-2 min-[860px]:grid-cols-1">
        <Linha vista={vista} camara="camara" />
        <Linha vista={vista} camara="senado" />
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <Link href="/previsao/" className={LIGACAO}>
          {t("inicio.previsao.ligacaoCompleta")}
        </Link>
        <Link href="/previsao/cenarios/" className={LIGACAO}>
          {t("inicio.previsao.ligacaoCenarios")}
        </Link>
      </p>
    </Painel>
  );
}
