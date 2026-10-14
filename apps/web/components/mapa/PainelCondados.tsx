import Link from "next/link";
import { Painel, type ReferenciaFonte } from "@/components/ui/Painel.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import {
  formatarMargemPontos as margem,
  formatarPercentagem,
  formatarPontos,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { SinalCondadosEstado } from "@/lib/voto-antecipado/condados.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function Variacao({ valor, texto }: { valor: number | null; texto: string }) {
  if (valor === null) return <span className="text-ink-3">—</span>;
  return <span className="text-ink-2">{texto}</span>;
}

/** De que condados vêm os votos antecipados, pela margem presidencial de 2024. */
export function PainelCondados({
  sinais,
  fontes,
}: {
  sinais: readonly SinalCondadosEstado[];
  fontes: readonly ReferenciaFonte[];
}) {
  if (sinais.length === 0) return null;
  const unicas = [...new Map(fontes.map((f) => [`${f.nome}|${f.url ?? ""}`, f])).values()];
  return (
    <Painel
      sobrelinha={t("mapa.condados.sobrelinha")}
      titulo={t("mapa.condados.titulo")}
      descricao={t("mapa.condados.texto")}
      fontes={unicas}
      metodo={t("mapa.condados.metodo")}
    >
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{t("mapa.condados.titulo")}</caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="pr-3 pb-1.5 font-medium">
              {t("mapa.condados.estado")}
            </th>
            <th scope="col" className="pr-3 pb-1.5 text-right font-medium">
              {t("mapa.condados.quotaTrump")}
            </th>
            <th scope="col" className="pb-1.5 text-right font-medium sm:pr-3">
              {t("mapa.condados.variacao")}
            </th>
            <th scope="col" className="hidden pb-1.5 text-right font-medium sm:table-cell">
              {t("mapa.condados.margem")}
            </th>
          </tr>
        </thead>
        <tbody className="font-mono text-[13px]">
          {sinais.map((s) => {
            const margemBase = s.base?.margem ?? null;
            return (
              <tr key={s.estado} className="border-t border-rule-2">
                <th scope="row" className="py-1.5 pr-3 text-left font-sans font-normal">
                  <Link href={caminhoEstado(s.estado)} className={LIGACAO}>
                    {nomeEstado(s.estado)}
                  </Link>
                </th>
                <td className="py-1.5 pr-3 text-right font-semibold">
                  {s.atual.quotaTrump === null ? "—" : formatarPercentagem(s.atual.quotaTrump)}
                </td>
                <td className="py-1.5 text-right sm:pr-3">
                  <Variacao valor={s.variacaoQuota} texto={formatarPontos(s.variacaoQuota ?? 0)} />
                  {s.base && s.variacaoQuota !== null ? (
                    <span className="block text-[11px] text-ink-3">
                      {t("mapa.condados.faceA", { ano: s.base.ano })}
                    </span>
                  ) : null}
                </td>
                <td className="hidden py-1.5 text-right sm:table-cell">
                  {s.atual.margem === null ? "—" : margem(s.atual.margem)}
                  {margemBase === null ? null : (
                    <span className="text-ink-3">
                      {" "}
                      {t("mapa.condados.margemBase", {
                        valor: margem(margemBase),
                        ano: s.base?.ano ?? "",
                      })}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[12.5px] text-ink-3">{t("mapa.condados.nota")}</p>
    </Painel>
  );
}
