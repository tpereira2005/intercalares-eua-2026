import { Painel } from "@/components/ui/Painel.tsx";
import {
  formatarMargemPontos,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type {
  ResumoVariante,
  VarianteVista,
  VistaSensibilidade,
} from "@/lib/previsao/sensibilidade.ts";
import { Estimativa } from "./PaginaPrevisao.tsx";

const NUMERO = "py-2 pl-3 text-right align-top font-mono text-[13px] whitespace-nowrap";

function Celula({ r, publicada }: { r: ResumoVariante; publicada: boolean }) {
  return (
    <td className={NUMERO}>
      <span className="block font-semibold">{formatarPercentagem(r.probD)}</span>
      <span className="block text-[11.5px] text-ink-2">
        {publicada
          ? t("previsao.sensibilidade.referencia")
          : Math.abs(r.variacao) < 0.0005
            ? t("previsao.sensibilidade.igual")
            : formatarPontos(r.variacao)}
      </span>
      <span className="block text-[11px] text-ink-3">
        {t("previsao.sensibilidade.lugares", { n: formatarNumero(r.lugaresMediana) })}
      </span>
    </td>
  );
}

function Linha({ v, publicada = false }: { v: VarianteVista; publicada?: boolean }) {
  return (
    <tr className={`border-t align-top ${publicada ? "border-ink-3" : "border-rule-2"}`}>
      <th scope="row" className="py-2 text-left font-normal">
        <span className="block font-semibold">{v.nome}</span>
        <span className="block text-[12.5px] text-ink-2">{v.descricao}</span>
        <span className="block font-mono text-[11.5px] text-ink-3">
          {t("previsao.sensibilidade.ambiente", { ambiente: formatarMargemPontos(v.ambiente) })}
        </span>
      </th>
      <Celula r={v.camara} publicada={publicada} />
      <Celula r={v.senado} publicada={publicada} />
    </tr>
  );
}

/**
 * Quanto mudam as probabilidades de controlo quando se altera uma escolha do modelo.
 * A primeira linha é a previsão publicada; as outras comparam-se com ela.
 */
export function PainelSensibilidade({ vista }: { vista: VistaSensibilidade }) {
  return (
    <Painel
      sobrelinha={t("previsao.sensibilidade.sobrelinha")}
      titulo={t("previsao.sensibilidade.titulo")}
      descricao={t("previsao.sensibilidade.texto")}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t("previsao.sensibilidade.metodo")}
    >
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{t("previsao.sensibilidade.legenda")}</caption>
        <thead>
          <tr className="rotulo">
            <th scope="col" className="pb-1.5 text-left font-medium">
              {t("previsao.sensibilidade.variante")}
            </th>
            <th scope="col" className="pb-1.5 pl-3 text-right font-medium">
              {t("previsao.sensibilidade.camara")}
            </th>
            <th scope="col" className="pb-1.5 pl-3 text-right font-medium">
              {t("previsao.sensibilidade.senado")}
            </th>
          </tr>
        </thead>
        <tbody>
          <Linha v={vista.publicada} publicada />
          {vista.variantes.map((v) => (
            <Linha key={v.nome} v={v} />
          ))}
        </tbody>
      </table>
    </Painel>
  );
}
