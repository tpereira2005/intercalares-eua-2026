import { formatarPercentagem, formatarPontos } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { BlocoCriterio, LinhaCriterio } from "@/lib/voto-antecipado/criterios.ts";

const CELULA =
  "py-1.5 pr-2 text-right font-mono whitespace-nowrap text-[12.5px] sm:pr-3 sm:text-[13px]";
const CABECALHO = "pr-2 pb-1.5 text-right font-medium sm:pr-3";

/** Amostra de cor só para o partido; as outras categorias não têm cor própria. */
const AMOSTRA: Partial<Record<LinhaCriterio["categoria"], string>> = {
  dem: "fundo-dem",
  rep: "fundo-rep",
  nao_afiliado: "fundo-una",
  outro: "bg-rule",
};

function rotulo(bloco: BlocoCriterio, linha: LinhaCriterio): string {
  switch (bloco.criterio) {
    case "partido":
      return t(`votoAntecipado.partidos.${linha.categoria as "dem"}`);
    case "modalidade":
      return t(`votoAntecipado.criterios.modalidades.${linha.categoria as "correio"}`);
    case "historico":
      return t(`votoAntecipado.criterios.historico.${linha.categoria as "novos"}`);
    case "idade":
      return linha.categoria.replace("-", "–");
  }
}

function Bloco({ bloco, ano }: { bloco: BlocoCriterio; ano: number }) {
  const titulo = t(`votoAntecipado.criterios.titulos.${bloco.criterio}`);
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <h3 className="rotulo">{titulo}</h3>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          {bloco.anoBase === null
            ? t("votoAntecipado.criterios.legendaSemBase", { criterio: titulo, ano })
            : t("votoAntecipado.criterios.legenda", { criterio: titulo, ano, base: bloco.anoBase })}
        </caption>
        <thead>
          <tr className="rotulo">
            <th scope="col" className="pr-3 pb-1.5 text-left font-medium">
              <span className="sr-only">{t("votoAntecipado.criterios.categoria")}</span>
            </th>
            <th scope="col" className={CABECALHO}>
              {ano}
            </th>
            {bloco.anoBase === null ? null : (
              <>
                <th scope="col" className={CABECALHO}>
                  {bloco.anoBase}
                </th>
                <th scope="col" className="pb-1.5 text-right font-medium">
                  {t("votoAntecipado.criterios.diferenca")}
                </th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {bloco.linhas.map((linha) => {
            const amostra = AMOSTRA[linha.categoria];
            return (
              <tr key={linha.categoria} className="border-t border-rule-2">
                <th scope="row" className="py-1.5 pr-3 text-left font-semibold">
                  {amostra ? (
                    <span
                      aria-hidden="true"
                      className={`mr-1.5 inline-block size-2.5 rounded-[1px] align-middle ${amostra}`}
                    />
                  ) : null}
                  {rotulo(bloco, linha)}
                </th>
                <td className={CELULA}>{formatarPercentagem(linha.quota)}</td>
                {bloco.anoBase === null ? null : (
                  <>
                    <td className={`${CELULA} text-ink-2`}>
                      {linha.quotaBase === null
                        ? t("comum.semDados")
                        : formatarPercentagem(linha.quotaBase)}
                    </td>
                    <td className="py-1.5 text-right font-mono text-[12.5px] whitespace-nowrap sm:text-[13px]">
                      {linha.quotaBase === null
                        ? t("comum.semDados")
                        : formatarPontos(linha.quota - linha.quotaBase)}
                    </td>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * "Quem já votou" pelos quatro critérios lado a lado, cada um face ao mesmo dia do ano
 * de referência. Nenhum critério tem destaque sobre os outros.
 */
export function QuemVotouCriterios({
  blocos,
  ano,
}: {
  blocos: readonly BlocoCriterio[];
  ano: number;
}) {
  if (blocos.length === 0) return null;
  return (
    // Colunas pela largura do painel, não do ecrã: o mesmo bloco vive no início e na
    // página de cada estado.
    <div className="@container">
      <div className="grid grid-cols-[minmax(0,1fr)] gap-x-6 gap-y-4 @[34rem]:grid-cols-2 @[64rem]:grid-cols-4">
        {blocos.map((b) => (
          <Bloco key={b.criterio} bloco={b} ano={ano} />
        ))}
      </div>
    </div>
  );
}
