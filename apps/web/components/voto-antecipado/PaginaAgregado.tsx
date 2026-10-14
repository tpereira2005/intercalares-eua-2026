import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import {
  formatarCompacto,
  formatarData,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { VistaAgregada } from "@/lib/voto-antecipado/agregado.ts";
import { resumirAgregado } from "@/lib/voto-antecipado/resumo.ts";
import { Avisos, EscolhaEstado } from "./PaginaEstado.tsx";
import { BarrasIdade, BarrasReserva, CurvaCoorte } from "./graficos.tsx";
import { AmostraAno, ItemLegenda, Legenda } from "./legendas.tsx";
import { PainelGeografia } from "./PainelGeografia.tsx";

const METODOLOGIA =
  "https://github.com/tpereira2005/intercalares-eua-2026/blob/main/docs/metodologia/voto-antecipado-estados.md";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function Indicadores({ vista }: { vista: VistaAgregada }) {
  const resumo = resumirAgregado(vista);
  const { anoBase, variacaoVotos, quota65, quota65Base, pendentes } = resumo;
  const pedidos = vista.pedidos.partidos.reduce((s, p) => s + p.pedidos, 0);
  const devolvidos = vista.pedidos.partidos.reduce((s, p) => s + p.devolvidos, 0);
  return (
    <FaixaKpis>
      <Kpi
        rotulo={t("agregado.kpis.votos")}
        valor={formatarCompacto(vista.votos)}
        {...(variacaoVotos === null || anoBase === null
          ? {}
          : {
              detalhe: t("agregado.kpis.votosDetalhe", {
                variacao: formatarVariacao(variacaoVotos),
                ano: anoBase,
              }),
            })}
      />
      {quota65 === null || quota65Base === null || anoBase === null ? null : (
        <Kpi
          rotulo={t("agregado.kpis.quota65")}
          valor={formatarPercentagem(quota65)}
          detalhe={t("agregado.kpis.quota65Detalhe", {
            pontos: formatarPontos(quota65 - quota65Base),
            ano: anoBase,
          })}
        />
      )}
      {pendentes === null || pedidos === 0 ? null : (
        <Kpi
          rotulo={t("agregado.kpis.pendentes")}
          valor={formatarCompacto(pendentes)}
          detalhe={t("agregado.kpis.pendentesDetalhe", {
            valor: formatarPercentagem(devolvidos / pedidos),
          })}
        />
      )}
    </FaixaKpis>
  );
}

/** Página de um estado sem ficheiro de eleitores: votos face a votos, no mesmo dia do ciclo. */
export function PaginaAgregado({
  vista,
  estados,
}: {
  vista: VistaAgregada;
  estados: readonly VistaAgregada["estado"][];
}) {
  const estado = nomeEstado(vista.estado);
  const qualidade = resumirAgregado(vista).qualidade;
  const fontes = vista.fontes
    .filter((f, i, todas) => todas.findIndex((g) => g.nome === f.nome) === i)
    .map((f) => ({ nome: f.nome, url: f.url }));
  const principal = vista.comparacoes[0];
  const anoBase = principal?.anoBase ?? null;
  const ano = vista.ano;
  const curvaAtual = vista.curvas.find((c) => c.ano === ano);
  const de = Math.max(...vista.curvas.flatMap((c) => c.pontos.map((p) => p.dias)), vista.diasAntes);
  const notas = vista.ciclos.filter((c) => c.notas.length > 0);

  const linhasIdade = principal
    ? principal.faixas.flatMap((f) =>
        f.quota === null
          ? []
          : [
              {
                faixa: f.categoria,
                valor: f.quota,
                referencias: vista.comparacoes.flatMap((c) => {
                  const base = c.faixas.find((x) => x.categoria === f.categoria)?.quotaBase ?? null;
                  return base === null ? [] : [{ ano: c.anoBase, valor: base }];
                }),
              },
            ],
      )
    : [];

  const partidos = (principal?.partidos ?? []).filter((p) => p.quota !== null);
  const pedidos = vista.pedidos.partidos;
  const modalidades = (principal?.modalidades ?? []).filter((m) => m.votos > 0);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("votoAntecipado.sobrelinha", { estado })}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t("agregado.titulo", { estado })}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
            {t(`agregado.lede.${vista.granularidade}`)}
          </p>
        </div>
        <div className="flex flex-col items-start gap-1.5 sm:items-end">
          <QualidadeDados nivel={qualidade} comTexto />
          <span className="font-mono text-[11px] text-ink-3">
            {t("votoAntecipado.dadosAte", {
              data: formatarData(new Date(`${vista.dadosAte}T12:00:00Z`)),
            })}
          </span>
        </div>
      </header>

      <EscolhaEstado atual={vista.estado} estados={estados} />

      <Indicadores vista={vista} />

      <Avisos avisos={vista.avisos} />

      {principal ? null : (
        <p className="rounded-md border border-rule bg-sheet px-[18px] py-3 text-sm text-ink-2">
          {t("agregado.semComparacao")}
        </p>
      )}

      <div className="grid gap-4 min-[860px]:grid-cols-2">
        {curvaAtual && vista.curvas.length > 1 ? (
          <Painel
            sobrelinha={t("agregado.ritmo.sobrelinha")}
            titulo={t("agregado.ritmo.titulo")}
            descricao={t("agregado.ritmo.texto")}
            fontes={fontes}
            metodo={t("agregado.ritmo.metodo")}
          >
            <Legenda>
              {vista.curvas
                .map((c) => c.ano)
                .sort((a, b) => (a === ano ? -1 : b === ano ? 1 : b - a))
                .map((a) => (
                  <ItemLegenda
                    key={a}
                    amostra={<AmostraAno ano={a} anoAtual={ano} vista={vista} forma="linha" />}
                  >
                    {a}
                  </ItemLegenda>
                ))}
            </Legenda>
            <CurvaCoorte
              titulo={t("agregado.ritmo.aria")}
              curvas={vista.curvas}
              anoAtual={ano}
              diasAntes={vista.diasAntes}
              comparacoes={vista.comparacoes}
              diaInicial={{ de, ate: 0 }}
              formato="numero"
            />
          </Painel>
        ) : null}

        {principal && linhasIdade.length > 0 ? (
          <Painel
            sobrelinha={t("agregado.idade.sobrelinha")}
            titulo={t("agregado.idade.titulo")}
            descricao={t("agregado.idade.texto")}
            fontes={fontes}
            metodo={t("agregado.idade.metodo")}
          >
            <Legenda>
              <ItemLegenda amostra={<AmostraAno ano={ano} anoAtual={ano} vista={vista} />}>
                {ano}
              </ItemLegenda>
              {vista.comparacoes.map((c) => (
                <ItemLegenda
                  key={c.anoBase}
                  amostra={<AmostraAno ano={c.anoBase} anoAtual={ano} vista={vista} />}
                >
                  {t("votoAntecipado.legenda.mesmoDia", { ano: c.anoBase })}
                </ItemLegenda>
              ))}
            </Legenda>
            <BarrasIdade
              titulo={t("votoAntecipado.graficos.composicaoAria", { ano })}
              linhas={linhasIdade}
              anoAtual={ano}
              anoComparar={principal.anoBase}
              comparacoes={vista.comparacoes}
            />
          </Painel>
        ) : null}

        {principal && partidos.length > 0 ? (
          <Painel
            sobrelinha={t("agregado.partido.sobrelinha")}
            titulo={t("agregado.partido.titulo")}
            descricao={t("agregado.partido.texto", { ano: principal.anoBase })}
            fontes={fontes}
            metodo={t("agregado.partido.metodo", { ano: principal.anoBase })}
          >
            <BarrasReserva
              titulo={t("agregado.partido.aria")}
              partidos={partidos.map((p) => ({
                partido: p.categoria,
                habituais: 0,
                jaVotaram: p.votos,
                restantes: 0,
                mobilizacao: p.quota,
                mobilizacaoBase: p.quotaBase,
              }))}
              detalhes={partidos.map((p) =>
                p.ritmo === null
                  ? formatarNumero(p.votos)
                  : t("agregado.partido.ritmo", {
                      valor: formatarVariacao(p.ritmo),
                      ano: principal.anoBase,
                    }),
              )}
              anoAtual={ano}
              comparacoes={vista.comparacoes}
              anoBase={principal.anoBase}
            />
          </Painel>
        ) : null}

        {pedidos.length > 0 ? (
          <Painel
            sobrelinha={t("agregado.pedidos.sobrelinha")}
            titulo={t("agregado.pedidos.titulo")}
            descricao={t("agregado.pedidos.texto", { ano: vista.pedidos.anoBase ?? anoBase ?? "" })}
            fontes={fontes}
            metodo={t("agregado.pedidos.metodo")}
          >
            <BarrasReserva
              titulo={t("agregado.pedidos.aria")}
              partidos={pedidos.map((p) => ({
                partido: p.partido,
                habituais: p.pedidos,
                jaVotaram: p.devolvidos,
                restantes: p.pendentes,
                mobilizacao: p.devolucao,
                mobilizacaoBase: p.devolucaoBase,
              }))}
              detalhes={pedidos.map((p) =>
                t("agregado.pedidos.pendentes", { valor: formatarNumero(p.pendentes) }),
              )}
              anoAtual={ano}
              comparacoes={vista.comparacoes}
              anoBase={vista.pedidos.anoBase}
            />
          </Painel>
        ) : null}

        {principal && modalidades.length > 1 ? (
          <Painel
            sobrelinha={t("agregado.modalidade.sobrelinha")}
            titulo={t("agregado.modalidade.titulo")}
            fontes={fontes}
            metodo={t("agregado.modalidade.metodo", { ano: principal.anoBase })}
          >
            <table className="w-full text-sm">
              <caption className="sr-only">{t("agregado.modalidade.titulo")}</caption>
              <thead>
                <tr>
                  <th scope="col" className="text-left">
                    <span className="sr-only">{t("agregado.modalidade.sobrelinha")}</span>
                  </th>
                  <th scope="col" className="rotulo pb-1.5 pl-4 text-right">
                    {t("agregado.modalidade.quota", { ano })}
                  </th>
                  <th scope="col" className="rotulo pb-1.5 pl-4 text-right">
                    {t("agregado.modalidade.ritmo", { ano: principal.anoBase })}
                  </th>
                </tr>
              </thead>
              <tbody>
                {modalidades.map((m) => (
                  <tr key={m.categoria}>
                    <th scope="row" className="py-0.5 text-left font-normal text-ink-2">
                      {t(`votoAntecipado.legenda.${m.categoria}`)}
                    </th>
                    <td className="py-0.5 pl-4 text-right font-semibold">
                      {m.quota === null ? t("comum.semDados") : formatarPercentagem(m.quota)}
                    </td>
                    <td className="py-0.5 pl-4 text-right font-semibold">
                      {m.ritmo === null ? t("comum.semDados") : formatarVariacao(m.ritmo)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Painel>
        ) : null}

        {principal && vista.geografia.length > 0 ? (
          <PainelGeografia
            unidades={vista.geografia}
            ano={ano}
            anoBase={principal.anoBase}
            fontes={fontes}
            comParticipacao={false}
            className="min-[860px]:col-span-2"
          />
        ) : null}

        <section className="self-start rounded-md border border-rule bg-sheet px-[18px] py-3.5 text-sm">
          <h2 className="rotulo mb-2">{t("votoAntecipado.notasCiclos")}</h2>
          {notas.length > 0 ? (
            <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[auto_minmax(0,1fr)]">
              {notas.map((ciclo) => (
                <div key={ciclo.ano} className="contents">
                  <dt className="font-mono text-ink">{ciclo.ano}</dt>
                  <dd className="text-ink-2">{ciclo.notas.join(" ")}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <p className="mt-3">
            <a href={METODOLOGIA} rel="noopener noreferrer" className={LIGACAO}>
              {t("agregado.documentacao")}
            </a>
          </p>
        </section>
      </div>
    </div>
  );
}
