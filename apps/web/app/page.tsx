import { CodigoDia } from "@/components/ui/CodigoDia.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { DIA_DA_ELEICAO, diasAteEleicao, formatarData } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";

export default function Inicio() {
  // Calculado no momento do build; o site é reconstruído a cada atualização de dados.
  const dias = diasAteEleicao(new Date());

  return (
    <>
      <h1 className="sr-only">{t("inicio.titulo")}</h1>
      <div className="grid gap-4 min-[860px]:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        <Painel
          sobrelinha={t("inicio.sobrelinha")}
          titulo={formatarData(DIA_DA_ELEICAO)}
          acessorio={<CodigoDia dias={dias} />}
          metodo={t("inicio.metodo")}
        >
          <div className="flex flex-wrap items-end gap-4">
            <span className="font-display text-[clamp(76px,11vw,128px)] leading-[0.82] font-black tracking-[-0.01em]">
              {dias}
            </span>
            <span className="pb-1.5 font-display text-[22px] leading-[1.05] font-bold tracking-[0.03em] uppercase">
              {dias > 0 ? t("inicio.diasParaEleicao") : t("inicio.diaDaEleicao")}
            </span>
          </div>
          <p className="max-w-[62ch] text-[16.5px] leading-relaxed">{t("inicio.emJogo")}</p>
        </Painel>
        <Painel titulo={t("inicio.proximosTitulo")} descricao={t("inicio.proximosDescricao")}>
          <ol className="flex flex-col">
            {(["votoAntecipado", "previsao", "noite"] as const).map((chave, indice) => (
              <li
                key={chave}
                className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 border-t border-rule-2 py-2.5 text-sm first:border-t-0"
              >
                <span className="font-mono text-xs text-ink-3">
                  {String(indice + 1).padStart(2, "0")}
                </span>
                <span>{t(`inicio.proximos.${chave}`)}</span>
              </li>
            ))}
          </ol>
        </Painel>
      </div>
    </>
  );
}
