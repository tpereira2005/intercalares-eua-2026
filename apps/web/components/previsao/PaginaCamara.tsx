import Link from "next/link";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import { nomeEstado } from "@/lib/estados.ts";
import {
  formatarData,
  formatarDataCurta,
  formatarMargemPontos as margem,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { DadosPrevisao } from "@/lib/previsao/carregar.ts";
import { caminhoMaioria, type CaminhoMaioria } from "@/lib/previsao/cenarios.ts";
import type {
  Camara,
  CorridaVista,
  Lado,
  VistaEvolucao,
  VistaPrevisao,
} from "@/lib/previsao/vista.ts";
import { EvolucaoControlo } from "./graficos.tsx";
import {
  Estimativa,
  PainelCamara,
  PainelLugares,
  PainelSenado,
  VersaoPrevisao,
  data,
} from "./PaginaPrevisao.tsx";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";
const LADOS: readonly Lado[] = ["D", "R"];

function Indicadores({ vista, camara }: { vista: VistaPrevisao; camara: Camara }) {
  const r = vista[camara];
  const lider = r.probD >= r.probR ? "D" : "R";
  const outro = lider === "D" ? "R" : "D";
  const prob = (lado: Lado) => (lado === "D" ? r.probD : r.probR);
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("previsao.paginas.kpis.controlo")}
        valor={`${lider} ${formatarPercentagem(prob(lider), 0)}`}
        detalhe={`${outro} ${formatarPercentagem(prob(outro), 0)}`}
      />
      <Kpi
        rotulo={t("previsao.paginas.kpis.lugares")}
        valor={String(r.mediana)}
        detalhe={t("previsao.paginas.kpis.lugaresDetalhe", {
          de: r.p10,
          ate: r.p90,
          maioria: r.maioria,
        })}
      />
      <Kpi
        rotulo={t("previsao.paginas.kpis.limiar")}
        valor={r.limiar === null ? "—" : margem(r.limiar)}
        detalhe={t("previsao.paginas.kpis.limiarDetalhe", {
          ambiente: margem(vista.ambiente.margem),
        })}
      />
    </FaixaKpis>
  );
}

function PainelEvolucaoCamara({
  vista,
  evolucao,
  camara,
}: {
  vista: VistaPrevisao;
  evolucao: VistaEvolucao | null;
  camara: Camara;
}) {
  const pontos = evolucao?.[camara] ?? [];
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  const dias = pontos.length;
  return (
    <Painel
      sobrelinha={t("previsao.evolucao.sobrelinha")}
      titulo={t("previsao.evolucao.titulo")}
      descricao={
        dias > 1 && primeiro
          ? t("previsao.paginas.evolucao", {
              camara: t(`previsao.camaraDa.${camara}`),
              de: formatarData(data(primeiro.corte)),
              n: dias,
            })
          : t("previsao.evolucao.umDia")
      }
      acessorio={dias > 1 ? <Estimativa /> : <Selo>{t("comum.emPreparacao")}</Selo>}
      fontes={vista.fontes}
      metodo={t("previsao.evolucao.metodo")}
    >
      {primeiro && ultimo ? (
        <>
          <EvolucaoControlo
            pontos={pontos}
            titulo={t("previsao.evolucao.aria", {
              camara: t(`previsao.camaraNa.${camara}`),
              de: formatarPercentagem(primeiro.probD, 0),
              ate: formatarPercentagem(ultimo.probD, 0),
            })}
          />
          {dias > 1 ? (
            <p className="font-mono text-[11px] text-ink-3">
              {t("previsao.evolucao.lugares", {
                de: primeiro.mediana,
                ate: ultimo.mediana,
                data: formatarDataCurta(data(primeiro.corte)),
              })}
            </p>
          ) : null}
        </>
      ) : null}
    </Painel>
  );
}

function nomeCurto(c: CorridaVista): string {
  if (c.camara === "camara") return c.id;
  const estado = nomeEstado(c.estado);
  return c.especial ? t("previsao.caminho.especial", { estado }) : estado;
}

function LeituraLimiar({
  caminho,
  vista,
  camara,
}: {
  caminho: CaminhoMaioria;
  vista: VistaPrevisao;
  camara: Camara;
}) {
  const { folga, lado } = caminho;
  const limiar = vista[camara].limiar;
  if (folga === null || limiar === null) {
    return <p className="text-sm text-ink-2">{t("previsao.caminho.semLimiar")}</p>;
  }
  const valores = {
    direcao: t(`previsao.caminho.direcao.${lado}`),
    limiar: margem(limiar),
    ambiente: margem(vista.ambiente.margem),
    pontos: Math.abs(folga).toLocaleString("pt-PT", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }),
  };
  return (
    <p className="text-sm text-ink-2">
      {folga >= 0
        ? t("previsao.caminho.favorito", valores)
        : t("previsao.caminho.precisaDeslocacao", valores)}
    </p>
  );
}

function CartaoCaminho({
  caminho,
  vista,
  camara,
  corridasTotal,
}: {
  caminho: CaminhoMaioria;
  vista: VistaPrevisao;
  camara: Camara;
  corridasTotal: number;
}) {
  const { lado } = caminho;
  const decisiva = caminho.corridas.find((c) => c.decisiva);
  return (
    <section
      aria-labelledby={`caminho-${camara}-${lado}`}
      className="flex min-w-0 flex-col gap-3 rounded-[3px] border border-rule p-3.5"
    >
      <header className="flex items-center justify-between gap-3">
        <h3
          id={`caminho-${camara}-${lado}`}
          className="flex items-center gap-2 text-[15px] font-semibold"
        >
          <span
            aria-hidden="true"
            className={`inline-block size-3 shrink-0 rounded-[2px] ${lado === "D" ? "fundo-dem" : "fundo-rep"}`}
          />
          {t(`previsao.partidos.${lado}`)}
        </h3>
        <span className="font-mono text-[13px] font-semibold">
          {formatarPercentagem(caminho.probControlo, 0)}
        </span>
      </header>
      <p className="text-sm">
        {caminho.foraDeJogo > 0
          ? t("previsao.caminho.precisaFora", {
              precisa: caminho.precisa,
              fora: caminho.foraDeJogo,
              n: caminho.vitoriasNecessarias,
              total: corridasTotal,
            })
          : t("previsao.caminho.precisa", {
              precisa: caminho.precisa,
              n: caminho.vitoriasNecessarias,
              total: corridasTotal,
            })}
        {decisiva
          ? ` ${t("previsao.caminho.decisiva", {
              corrida: nomeCurto(decisiva.corrida),
              prob: formatarPercentagem(decisiva.prob, 0),
            })}`
          : null}
      </p>
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">
          {t("previsao.caminho.legendaTabela", { partido: t(`previsao.partidos.${lado}`) })}
        </caption>
        <thead>
          <tr className="rotulo text-left">
            <th scope="col" className="w-10 pr-2 pb-1.5 font-medium">
              {t("previsao.caminho.posicao")}
            </th>
            <th scope="col" className="pr-3 pb-1.5 font-medium">
              {t("previsao.tabela.corrida")}
            </th>
            <th scope="col" className="pb-1.5 text-right font-medium">
              {t("previsao.caminho.prob")}
            </th>
          </tr>
        </thead>
        <tbody>
          {caminho.corridas.map((c) => (
            <tr
              key={c.corrida.id}
              className={`border-t border-rule-2 ${c.decisiva ? "bg-signal-wash" : ""}`}
            >
              <td className="py-1.5 pr-2 font-mono text-[12.5px] text-ink-3">{c.posicao}.</td>
              <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                <Link href={caminhoPaginaCorrida(c.corrida.id)} className={LIGACAO}>
                  {nomeCurto(c.corrida)}
                </Link>
                {c.decisiva ? (
                  <span className="ml-2 font-mono text-[11px] font-semibold text-ink-2 uppercase">
                    {t("previsao.caminho.marcaDecisiva")}
                  </span>
                ) : null}
              </th>
              <td className="py-1.5 text-right font-mono text-[13px]">
                {formatarPercentagem(c.prob, 0)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <LeituraLimiar caminho={caminho} vista={vista} camara={camara} />
    </section>
  );
}

function PainelCaminhos({ vista, camara }: { vista: VistaPrevisao; camara: Camara }) {
  const caminhos = LADOS.map((lado) => caminhoMaioria(vista, camara, lado)).filter(
    (c): c is CaminhoMaioria => c !== null,
  );
  if (caminhos.length === 0) return null;
  const corridasTotal = (camara === "senado" ? vista.corridasSenado : vista.corridasCamara).length;
  return (
    <Painel
      sobrelinha={t("previsao.caminho.sobrelinha")}
      titulo={t("previsao.caminho.titulo")}
      descricao={t("previsao.caminho.texto")}
      acessorio={<Estimativa />}
      fontes={vista.fontes}
      metodo={t("previsao.caminho.metodo", { simulacoes: formatarNumero(vista.simulacoes) })}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {caminhos.map((c) => (
          <CartaoCaminho
            key={c.lado}
            caminho={c}
            vista={vista}
            camara={camara}
            corridasTotal={corridasTotal}
          />
        ))}
      </div>
    </Painel>
  );
}

/** Página da previsão de uma só câmara: /previsao/camara/ e /previsao/senado/. */
export function PaginaCamara({ dados, camara }: { dados: DadosPrevisao; camara: Camara }) {
  const { previsao: vista, evolucao } = dados;
  const r = vista[camara];
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("previsao.sobrelinha", { ano: vista.ano })}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t(`previsao.paginas.${camara}.titulo`)}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
            {t(`previsao.paginas.${camara}.lede`, {
              maioria: r.maioria,
              n: (camara === "senado" ? vista.corridasSenado : vista.corridasCamara).length,
              fora: r.foraDeJogo.D + r.foraDeJogo.R,
            })}
          </p>
        </div>
        <VersaoPrevisao vista={vista} />
      </header>

      <Indicadores vista={vista} camara={camara} />

      <div className="grid gap-4 min-[860px]:grid-cols-2">
        <PainelLugares vista={vista} camara={camara} />
        <PainelEvolucaoCamara vista={vista} evolucao={evolucao} camara={camara} />
      </div>

      <PainelCaminhos vista={vista} camara={camara} />

      {camara === "senado" ? (
        <PainelSenado vista={vista} evolucao={evolucao} />
      ) : (
        <PainelCamara vista={vista} evolucao={evolucao} todos />
      )}

      <p className="text-sm">
        <Link href="/previsao/" className={LIGACAO}>
          {t("previsao.paginas.voltar")}
        </Link>
      </p>
    </div>
  );
}
