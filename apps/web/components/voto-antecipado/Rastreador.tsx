"use client";

import { useState, type ReactNode } from "react";
import { ControloSegmentado } from "@/components/ui/ControloSegmentado.tsx";
import { Painel, type ReferenciaFonte } from "@/components/ui/Painel.tsx";
import { formatarData, formatarDiaCiclo, formatarPontos } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import {
  DIAS_CURVA,
  FAIXAS,
  type FaixaEtaria,
  type VistaVotoAntecipado,
} from "@/lib/voto-antecipado/vista.ts";
import { estiloAno, rotuloFaixa } from "./anos.ts";
import {
  BarrasDesvio,
  BarrasIdade,
  BarrasMomento,
  BarrasReserva,
  CurvaCoorte,
  Cruzamento,
  Decomposicao,
} from "./graficos.tsx";

type Pergunta = "composicao" | "participacao" | "momento";
type Janela = "ateHoje" | "cicloCompleto";

/* ---------- Legendas ---------- */

function Legenda({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-ink-2">
      {children}
    </div>
  );
}

function ItemLegenda({ amostra, children }: { amostra: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden="true" className="inline-flex">
        {amostra}
      </span>
      {children}
    </span>
  );
}

function AmostraAno({
  ano,
  anoAtual,
  vista,
  forma = "traco",
}: {
  ano: number;
  anoAtual: number;
  vista: VistaVotoAntecipado;
  forma?: "traco" | "linha";
}) {
  const estilo = estiloAno(ano, anoAtual, vista.comparacoes);
  if (ano === anoAtual && forma === "traco") {
    return <span className="inline-block h-2.5 w-3.5 rounded-[1px] bg-signal" />;
  }
  return (
    <svg width={forma === "traco" ? 6 : 16} height={12}>
      {forma === "traco" ? (
        <line
          x1={3}
          x2={3}
          y1={0}
          y2={12}
          strokeWidth={2}
          strokeDasharray={estilo.tracejado ? "3 2" : undefined}
          className={estilo.classe}
        />
      ) : (
        <line
          x1={0}
          x2={16}
          y1={6}
          y2={6}
          strokeWidth={Math.min(estilo.largura, 2.5)}
          strokeDasharray={estilo.tracejado}
          className={estilo.classe}
        />
      )}
    </svg>
  );
}

function Amostra({ className, fill }: { className?: string; fill?: string }) {
  return (
    <svg width={14} height={10}>
      <rect width={14} height={10} className={className} fill={fill} />
    </svg>
  );
}

/* ---------- Escolha da faixa ---------- */

function Fichas({
  faixas,
  ativa,
  aoEscolher,
}: {
  faixas: readonly { valor: string; rotulo: string }[];
  ativa: string;
  aoEscolher: (valor: string) => void;
}) {
  return (
    <div role="group" aria-label={t("votoAntecipado.faixaAria")} className="flex flex-wrap gap-1.5">
      {faixas.map((f) => (
        <button
          key={f.valor}
          type="button"
          aria-pressed={f.valor === ativa}
          onClick={() => {
            aoEscolher(f.valor);
          }}
          className={`cursor-pointer rounded-[2px] border px-2 py-1 font-mono text-[12px] leading-none ${
            f.valor === ativa
              ? "border-signal bg-signal-wash text-signal-ink"
              : "border-rule text-ink-2 hover:text-ink"
          }`}
        >
          {f.rotulo}
        </button>
      ))}
    </div>
  );
}

function Texto({ children }: { children: ReactNode }) {
  return <p className="max-w-[70ch] text-sm text-ink-2">{children}</p>;
}

/* ---------- Rastreador ---------- */

export function Rastreador({
  vista,
  fontes,
  rodape,
}: {
  vista: VistaVotoAntecipado;
  fontes: readonly ReferenciaFonte[];
  /** Última célula da grelha (notas e metodologia). */
  rodape?: ReactNode;
}) {
  const principal = vista.comparacoes[0];
  const [pergunta, setPergunta] = useState<Pergunta>("composicao");
  const [anoComparar, setAnoComparar] = useState<number>(principal?.anoBase ?? vista.ano);
  const [faixa, setFaixa] = useState<FaixaEtaria>("18-24");
  const [faixaCurva, setFaixaCurva] = useState<FaixaEtaria | "total">("18-24");
  const [cruzamento, setCruzamento] = useState<"partido" | "modalidade">("partido");
  const [janela, setJanela] = useState<Janela>("ateHoje");

  const escolher = (f: FaixaEtaria) => {
    setFaixa(f);
    setFaixaCurva(f);
  };
  const comparacao = vista.comparacoes.find((c) => c.anoBase === anoComparar) ?? principal;
  if (!comparacao) return null;
  const ano = vista.ano;
  const dia = formatarDiaCiclo(vista.diasAntes);
  const linhaFaixa = comparacao.faixas.find((f) => f.faixa === faixa);
  const momentoAtual = vista.momento.find((m) => m.ano === ano);
  const momentoBase = vista.momento.find((m) => m.ano === anoComparar);
  const referencia = vista.anoReferenciaHistorico ?? anoComparar;

  const linhasBarras = FAIXAS.flatMap((f) => {
    const atual = comparacao.faixas.find((l) => l.faixa === f);
    if (!atual) return [];
    const valor = pergunta === "participacao" ? atual.taxa : atual.quota;
    if (valor === null) return [];
    return [
      {
        faixa: f,
        valor,
        referencias: vista.comparacoes.flatMap((c) => {
          const l = c.faixas.find((x) => x.faixa === f);
          const v = l ? (pergunta === "participacao" ? l.taxaBase : l.quotaBase) : null;
          return v === null ? [] : [{ ano: c.anoBase, valor: v }];
        }),
      },
    ];
  });

  const fichasFaixa = FAIXAS.map((f) => ({ valor: f, rotulo: rotuloFaixa(f) }));
  const rotuloCurva = faixaCurva === "total" ? null : rotuloFaixa(faixaCurva);

  return (
    <div className="flex flex-col gap-4">
      <div
        role="group"
        aria-label={t("votoAntecipado.controlosAria")}
        className="flex flex-wrap items-end gap-x-6 gap-y-3 rounded-md border border-rule bg-sheet px-[18px] py-3"
      >
        <div className="flex flex-col gap-1.5">
          <span className="rotulo">{t("votoAntecipado.perguntas.rotulo")}</span>
          <ControloSegmentado<Pergunta>
            rotuloGrupo={t("votoAntecipado.perguntas.rotulo")}
            valor={pergunta}
            aoMudar={setPergunta}
            opcoes={[
              { valor: "composicao", rotulo: t("votoAntecipado.perguntas.composicao") },
              { valor: "participacao", rotulo: t("votoAntecipado.perguntas.participacao") },
              { valor: "momento", rotulo: t("votoAntecipado.perguntas.momento") },
            ]}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="rotulo">{t("votoAntecipado.comparar.rotulo")}</span>
          <ControloSegmentado<string>
            rotuloGrupo={t("votoAntecipado.comparar.rotulo")}
            valor={String(anoComparar)}
            aoMudar={(v) => {
              setAnoComparar(Number(v));
            }}
            opcoes={vista.comparacoes.map((c) => ({
              valor: String(c.anoBase),
              rotulo: String(c.anoBase),
            }))}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="rotulo">{t("votoAntecipado.diaDoCiclo")}</span>
          <span className="py-1.5 text-[13px] text-ink-2">
            <span className="mr-2 rounded-[2px] bg-signal-wash px-1.5 py-1 font-mono text-xs font-medium text-signal-ink">
              {dia}
            </span>
            {t("votoAntecipado.dadosAte", {
              data: formatarData(new Date(`${vista.dadosAte}T12:00:00Z`)),
            })}
          </span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Painel
          className="lg:col-span-2"
          sobrelinha={`${t("votoAntecipado.perguntas.rotulo")} · ${t(`votoAntecipado.perguntas.${pergunta}`)}`}
          titulo={t(`votoAntecipado.perguntas.${pergunta}Titulo`)}
          fontes={fontes}
          metodo={t(`votoAntecipado.metodo.${pergunta}`, { referencia })}
        >
          <Texto>
            {pergunta === "momento"
              ? t("votoAntecipado.perguntas.momentoTexto", { referencia })
              : t(`votoAntecipado.perguntas.${pergunta}Texto`)}
          </Texto>
          {pergunta === "momento" ? (
            momentoAtual ? (
              <>
                <Legenda>
                  <ItemLegenda amostra={<Amostra className="fill-ink-3 opacity-45" />}>
                    {t("votoAntecipado.legenda.habituais")}
                  </ItemLegenda>
                  <ItemLegenda amostra={<Amostra fill="url(#padrao-antecipacao)" />}>
                    {t("votoAntecipado.legenda.antecipacao")}
                  </ItemLegenda>
                  <ItemLegenda amostra={<Amostra className="fill-up" />}>
                    {t("votoAntecipado.legenda.novos")}
                  </ItemLegenda>
                </Legenda>
                <BarrasMomento
                  titulo={t("votoAntecipado.graficos.momentoAria", { ano })}
                  linhas={momentoAtual.faixas}
                  {...(momentoBase
                    ? { base: { ano: momentoBase.ano, linhas: momentoBase.faixas } }
                    : {})}
                  faixaAtiva={faixa}
                  aoEscolher={escolher}
                />
              </>
            ) : (
              <Texto>{t("votoAntecipado.perguntas.momentoSemHistorico")}</Texto>
            )
          ) : (
            <>
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
                <span className="text-ink-3">
                  {t("votoAntecipado.legenda.variacaoFace", { ano: anoComparar })}
                </span>
              </Legenda>
              <BarrasIdade
                titulo={t(
                  pergunta === "participacao"
                    ? "votoAntecipado.graficos.participacaoAria"
                    : "votoAntecipado.graficos.composicaoAria",
                  { ano },
                )}
                linhas={linhasBarras}
                anoAtual={ano}
                anoComparar={anoComparar}
                comparacoes={vista.comparacoes}
                faixaAtiva={faixa}
                aoEscolher={escolher}
              />
            </>
          )}
        </Painel>

        <Painel
          sobrelinha={t("votoAntecipado.desvio.sobrelinha", { ano: anoComparar })}
          titulo={t("votoAntecipado.desvio.titulo")}
          fontes={fontes}
          metodo={t("votoAntecipado.metodo.desvio", { ano: anoComparar })}
        >
          <Texto>{t("votoAntecipado.desvio.texto", { ano: anoComparar })}</Texto>
          <Legenda>
            <ItemLegenda amostra={<Amostra className="fill-up" />}>
              {t("votoAntecipado.legenda.acima")}
            </ItemLegenda>
            <ItemLegenda amostra={<Amostra className="fill-down" />}>
              {t("votoAntecipado.legenda.abaixo")}
            </ItemLegenda>
          </Legenda>
          <BarrasDesvio
            titulo={t("votoAntecipado.graficos.desvioAria")}
            linhas={comparacao.faixas}
            faixaAtiva={faixa}
            aoEscolher={escolher}
          />
        </Painel>

        <Painel
          sobrelinha={t("votoAntecipado.decomposicao.sobrelinha", {
            faixa: rotuloFaixa(faixa),
            ano,
            base: anoComparar,
            dia,
          })}
          titulo={t("votoAntecipado.decomposicao.titulo")}
          fontes={fontes}
          metodo={t("votoAntecipado.metodo.decomposicao")}
        >
          {linhaFaixa ? (
            <Texto>
              {t("votoAntecipado.decomposicao.texto", {
                faixa: rotuloFaixa(faixa),
                total: formatarPontos(linhaFaixa.quota - linhaFaixa.quotaBase, 2),
                recenseamento: formatarPontos(linhaFaixa.efeitoRecenseamento, 2),
                participacao: formatarPontos(linhaFaixa.efeitoParticipacao, 2),
              })}
            </Texto>
          ) : null}
          <Fichas
            faixas={fichasFaixa}
            ativa={faixa}
            aoEscolher={(v) => {
              escolher(v as FaixaEtaria);
            }}
          />
          {linhaFaixa ? (
            <Decomposicao
              titulo={t("votoAntecipado.graficos.decomposicaoAria", { faixa: rotuloFaixa(faixa) })}
              recenseamento={linhaFaixa.efeitoRecenseamento}
              participacao={linhaFaixa.efeitoParticipacao}
            />
          ) : null}
        </Painel>

        <Painel
          sobrelinha={t("votoAntecipado.curva.sobrelinha")}
          titulo={
            rotuloCurva === null
              ? t("votoAntecipado.curva.tituloTotal")
              : t("votoAntecipado.curva.titulo", { faixa: rotuloCurva })
          }
          acessorio={
            <ControloSegmentado<Janela>
              rotuloGrupo={t("votoAntecipado.curva.janelaAria")}
              valor={janela}
              aoMudar={setJanela}
              opcoes={[
                { valor: "ateHoje", rotulo: t("votoAntecipado.curva.ateHoje") },
                { valor: "cicloCompleto", rotulo: t("votoAntecipado.curva.cicloCompleto") },
              ]}
            />
          }
          fontes={fontes}
          metodo={t("votoAntecipado.metodo.curva")}
        >
          <Fichas
            faixas={[...fichasFaixa, { valor: "total", rotulo: t("votoAntecipado.curva.todas") }]}
            ativa={faixaCurva}
            aoEscolher={(v) => {
              if (v === "total") setFaixaCurva("total");
              else escolher(v as FaixaEtaria);
            }}
          />
          <Legenda>
            {[ano, ...vista.comparacoes.map((c) => c.anoBase)].map((a) => (
              <ItemLegenda
                key={a}
                amostra={<AmostraAno ano={a} anoAtual={ano} vista={vista} forma="linha" />}
              >
                {a}
              </ItemLegenda>
            ))}
          </Legenda>
          <CurvaCoorte
            titulo={t("votoAntecipado.graficos.curvaAria", {
              faixa: rotuloCurva ?? t("votoAntecipado.curva.todas"),
            })}
            curvas={vista.curvas[faixaCurva]}
            anoAtual={ano}
            diasAntes={vista.diasAntes}
            comparacoes={vista.comparacoes}
            diaInicial={{
              de: DIAS_CURVA,
              ate: janela === "ateHoje" ? vista.diasAntes : 0,
            }}
          />
        </Painel>

        <Painel
          sobrelinha={t("votoAntecipado.cruzamento.sobrelinha", { ano })}
          titulo={t(
            cruzamento === "partido"
              ? "votoAntecipado.cruzamento.tituloPartido"
              : "votoAntecipado.cruzamento.tituloModalidade",
          )}
          acessorio={
            <ControloSegmentado<"partido" | "modalidade">
              rotuloGrupo={t("votoAntecipado.cruzamento.modoAria")}
              valor={cruzamento}
              aoMudar={setCruzamento}
              opcoes={[
                { valor: "partido", rotulo: t("votoAntecipado.cruzamento.partido") },
                { valor: "modalidade", rotulo: t("votoAntecipado.cruzamento.modalidade") },
              ]}
            />
          }
          fontes={fontes}
          metodo={t("votoAntecipado.metodo.cruzamento", { ano })}
        >
          <Legenda>
            {cruzamento === "partido" ? (
              <>
                <ItemLegenda amostra={<Amostra className="fill-dem" />}>
                  {t("votoAntecipado.partidos.dem")}
                </ItemLegenda>
                <ItemLegenda amostra={<Amostra fill="url(#padrao-rep)" />}>
                  {t("votoAntecipado.partidos.rep")}
                </ItemLegenda>
                <ItemLegenda amostra={<Amostra fill="url(#padrao-una)" />}>
                  {t("votoAntecipado.partidos.nao_afiliado")}
                </ItemLegenda>
                <ItemLegenda amostra={<Amostra className="fill-rule" />}>
                  {t("votoAntecipado.partidos.outro")}
                </ItemLegenda>
                {vista.anoCruzamentos === null ? null : (
                  <span className="text-ink-3">
                    {t("votoAntecipado.legenda.variacaoDemRep", { ano: vista.anoCruzamentos })}
                  </span>
                )}
              </>
            ) : (
              <>
                <ItemLegenda amostra={<Amostra className="fill-ink-2" />}>
                  {t("votoAntecipado.legenda.correio")}
                </ItemLegenda>
                <ItemLegenda amostra={<Amostra className="fill-ink-3 opacity-30" />}>
                  {t("votoAntecipado.legenda.presencial")}
                </ItemLegenda>
              </>
            )}
          </Legenda>
          <Cruzamento
            titulo={t(
              cruzamento === "partido"
                ? "votoAntecipado.graficos.cruzamentoPartidoAria"
                : "votoAntecipado.graficos.cruzamentoModalidadeAria",
            )}
            linhas={vista.cruzamentos}
            modo={cruzamento}
            faixaAtiva={faixa}
            aoEscolher={escolher}
          />
          {cruzamento === "partido" ? (
            <p className="text-[12.5px] text-ink-3">{t("votoAntecipado.cruzamento.nota")}</p>
          ) : null}
        </Painel>

        {vista.reserva.partidos.length > 0 ? (
          <Painel
            sobrelinha={t("votoAntecipado.reserva.sobrelinha")}
            titulo={t("votoAntecipado.reserva.titulo")}
            fontes={fontes}
            metodo={t("votoAntecipado.metodo.reserva", { referencia })}
          >
            <Texto>
              {t("votoAntecipado.reserva.texto", {
                referencia,
                ano,
                base: vista.reserva.anoBase ?? referencia,
              })}
            </Texto>
            {vista.reserva.anoBase === null ? null : (
              <Legenda>
                <ItemLegenda
                  amostra={<AmostraAno ano={vista.reserva.anoBase} anoAtual={ano} vista={vista} />}
                >
                  {t("votoAntecipado.legenda.mesmoDia", { ano: vista.reserva.anoBase })}
                </ItemLegenda>
              </Legenda>
            )}
            <BarrasReserva
              titulo={t("votoAntecipado.graficos.reservaAria")}
              partidos={vista.reserva.partidos}
              anoAtual={ano}
              comparacoes={vista.comparacoes}
              anoBase={vista.reserva.anoBase}
            />
          </Painel>
        ) : null}
        {rodape}
      </div>
    </div>
  );
}
