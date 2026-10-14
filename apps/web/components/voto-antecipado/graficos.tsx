"use client";

import {
  FundoLinha,
  Grafico,
  HALO,
  afastarRotulos,
  escala,
  linhaEscolhivel,
} from "@/components/charts/base.tsx";
import {
  formatarCompacto,
  formatarDiaCiclo,
  formatarNumero,
  formatarPercentagem,
  formatarPontos,
  formatarVariacao,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { FaixaAgregada } from "@/lib/voto-antecipado/agregado.ts";
import {
  PARTIDOS,
  type CruzamentoFaixa,
  type CurvaAno,
  type FaixaEtaria,
  type MomentoFaixa,
  type PartidoRegisto,
  type ReservaPartido,
} from "@/lib/voto-antecipado/vista.ts";
import { estiloAno, rotuloFaixa, type AnoComparado, type LinhaBarra } from "./anos.ts";

const ROTULO = 54;
const TEXTO_EIXO = "fill-ink-3 font-mono text-[10.5px]";

/** Casas decimais que mantêm visíveis valores pequenos (ex.: 0,18%). */
function casas(maximo: number): number {
  return maximo <= 0.05 ? 2 : 1;
}

/** Casas decimais (em percentagem) que escrevem todas as marcas de um eixo sem arredondar. */
function casasMarcas(marcas: readonly number[]): number {
  for (let d = 0; d < 3; d++) {
    if (marcas.every((m) => Math.abs(Math.round(m * 100 * 10 ** d) - m * 100 * 10 ** d) < 1e-6)) {
      return d;
    }
  }
  return 3;
}

/** Preenchimento de cada partido: cor sólida para D, padrões para R e não filiados. */
export const PREENCHIMENTO_PARTIDO: Record<PartidoRegisto, { classe?: string; fill?: string }> = {
  dem: { classe: "fill-dem" },
  rep: { fill: "url(#padrao-rep)" },
  nao_afiliado: { fill: "url(#padrao-una)" },
  outro: { classe: "fill-rule" },
};

function RetanguloPartido({
  partido,
  ...props
}: {
  partido: PartidoRegisto;
  x: number;
  y: number;
  width: number;
  height: number;
}) {
  const p = PREENCHIMENTO_PARTIDO[partido];
  return <rect {...props} className={p.classe} fill={p.fill} />;
}

function Grelha({
  valores,
  x,
  topo,
  fundo,
  formatar,
}: {
  valores: readonly number[];
  x: (valor: number) => number;
  topo: number;
  fundo: number;
  formatar: (valor: number) => string;
}) {
  return (
    <g aria-hidden="true">
      {valores.map((valor) => (
        <g key={valor}>
          <line
            x1={x(valor)}
            x2={x(valor)}
            y1={topo - 4}
            y2={fundo}
            className={valor === 0 ? "stroke-ink-3" : "stroke-rule-2"}
          />
          <text x={x(valor)} y={topo - 10} textAnchor="middle" className={TEXTO_EIXO}>
            {formatar(valor)}
          </text>
        </g>
      ))}
    </g>
  );
}

/* ---------- Composição e participação por idade ---------- */

export function BarrasIdade<F extends FaixaAgregada = FaixaEtaria>({
  titulo,
  linhas,
  anoAtual,
  anoComparar,
  comparacoes,
  faixaAtiva,
  aoEscolher,
  compacto = false,
}: {
  titulo: string;
  linhas: readonly LinhaBarra<F>[];
  anoAtual: number;
  anoComparar: number;
  comparacoes: readonly AnoComparado[];
  /** Sem faixa ativa nem escolha, o gráfico é só de leitura (painel inicial). */
  faixaAtiva?: F;
  aoEscolher?: (faixa: F) => void;
  compacto?: boolean;
}) {
  const alturaLinha = compacto ? 30 : 36;
  const topo = 22;
  const altura = topo + linhas.length * alturaLinha + 4;
  const { maximo, marcas } = escala(
    Math.max(...linhas.flatMap((l) => [l.valor, ...l.referencias.map((r) => r.valor)]), 0.001),
  );
  const decimais = casas(maximo);
  return (
    <Grafico titulo={titulo} altura={altura} interativo={aoEscolher !== undefined}>
      {(largura) => {
        const colunaValor = largura < 480 ? 116 : 140;
        const x1 = largura - colunaValor;
        const x = (v: number) => ROTULO + ((x1 - ROTULO) * v) / maximo;
        return (
          <>
            <Grelha
              valores={marcas}
              x={x}
              topo={topo}
              fundo={altura - 2}
              formatar={(v) => formatarPercentagem(v, casasMarcas(marcas))}
            />
            {linhas.map((linha, indice) => {
              const y = topo + indice * alturaLinha;
              const centro = y + alturaLinha / 2;
              const ativa = linha.faixa === faixaAtiva;
              const referencia = linha.referencias.find((r) => r.ano === anoComparar);
              const valor = formatarPercentagem(linha.valor, decimais);
              const diferenca = referencia
                ? formatarPontos(linha.valor - referencia.valor, decimais)
                : null;
              return (
                <g
                  key={linha.faixa}
                  {...linhaEscolhivel(
                    referencia && diferenca !== null
                      ? t("votoAntecipado.graficos.linhaFaixaComparada", {
                          faixa: rotuloFaixa(linha.faixa),
                          valor,
                          diferenca,
                          ano: referencia.ano,
                        })
                      : t("votoAntecipado.graficos.linhaFaixa", {
                          faixa: rotuloFaixa(linha.faixa),
                          valor,
                        }),
                    aoEscolher
                      ? () => {
                          aoEscolher(linha.faixa);
                        }
                      : undefined,
                    ativa,
                  )}
                >
                  <FundoLinha y={y} largura={largura} altura={alturaLinha} ativa={ativa} />
                  <text
                    x={4}
                    y={centro + 4}
                    className={`fill-ink text-[13px] ${ativa ? "font-bold" : "font-medium"}`}
                  >
                    {rotuloFaixa(linha.faixa)}
                  </text>
                  <rect
                    x={ROTULO}
                    y={centro - 7}
                    width={Math.max(0, x(linha.valor) - ROTULO)}
                    height={14}
                    rx={1}
                    className="fill-signal"
                  />
                  {linha.referencias.map((r) => {
                    const estilo = estiloAno(r.ano, anoAtual, comparacoes);
                    return (
                      <line
                        key={r.ano}
                        x1={x(r.valor)}
                        x2={x(r.valor)}
                        y1={y + 5}
                        y2={y + alturaLinha - 5}
                        strokeWidth={2}
                        strokeDasharray={estilo.tracejado ? "3 2" : undefined}
                        className={estilo.classe}
                      />
                    );
                  })}
                  <text x={x1 + 10} y={centro + 4} className="fill-ink text-[13.5px] font-semibold">
                    {valor}
                  </text>
                  {referencia ? (
                    <text
                      x={x1 + (largura < 480 ? 62 : 74)}
                      y={centro + 4}
                      className="fill-ink-2 font-mono text-[11.5px]"
                    >
                      {diferenca}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </>
        );
      }}
    </Grafico>
  );
}

/* ---------- Momento do voto ---------- */

export function BarrasMomento({
  titulo,
  linhas,
  base,
  faixaAtiva,
  aoEscolher,
}: {
  titulo: string;
  linhas: readonly MomentoFaixa[];
  /** O mesmo grupo no mesmo dia do ano de referência, para comparação. */
  base?: { ano: number; linhas: readonly MomentoFaixa[] };
  faixaAtiva: FaixaEtaria;
  aoEscolher: (faixa: FaixaEtaria) => void;
}) {
  const alturaLinha = 36;
  const topo = 8;
  const faixas = linhas.filter(
    (l): l is MomentoFaixa & { faixa: FaixaEtaria } => l.faixa !== "total",
  );
  const altura = topo + faixas.length * alturaLinha + 4;
  return (
    <Grafico titulo={titulo} altura={altura} interativo>
      {(largura) => {
        const colunaValor = largura < 480 ? 92 : 150;
        const x1 = largura - colunaValor;
        const util = x1 - ROTULO;
        return faixas.map((linha, indice) => {
          const y = topo + indice * alturaLinha;
          const centro = y + alturaLinha / 2;
          const ativa = linha.faixa === faixaAtiva;
          const partes = [
            { chave: "habituais", valor: linha.habituais, classe: "fill-ink-3 opacity-45" },
            { chave: "antecipacao", valor: linha.antecipacao, fill: "url(#padrao-antecipacao)" },
            { chave: "novos", valor: linha.novos, classe: "fill-up" },
          ] as const;
          const novos = formatarPercentagem(linha.novos, 0);
          const daBase = base?.linhas.find((l) => l.faixa === linha.faixa);
          const rotulo = t("votoAntecipado.graficos.linhaMomento", {
            faixa: rotuloFaixa(linha.faixa),
            habituais: formatarPercentagem(linha.habituais, 0),
            antecipacao: formatarPercentagem(linha.antecipacao, 0),
            novos,
          });
          let x = ROTULO;
          return (
            <g
              key={linha.faixa}
              {...linhaEscolhivel(
                base && daBase
                  ? t("votoAntecipado.graficos.linhaMomentoBase", {
                      linha: rotulo,
                      ano: base.ano,
                      valor: formatarPercentagem(daBase.novos, 0),
                    })
                  : rotulo,
                () => {
                  aoEscolher(linha.faixa);
                },
                ativa,
              )}
            >
              <FundoLinha y={y} largura={largura} altura={alturaLinha} ativa={ativa} />
              <text
                x={4}
                y={centro + 4}
                className={`fill-ink text-[13px] ${ativa ? "font-bold" : "font-medium"}`}
              >
                {rotuloFaixa(linha.faixa)}
              </text>
              {partes.map((parte) => {
                const w = util * parte.valor;
                const inicio = x;
                x += w;
                return (
                  <g key={parte.chave}>
                    <rect
                      x={inicio}
                      y={centro - 8}
                      width={Math.max(0, w - 1)}
                      height={16}
                      className={"classe" in parte ? parte.classe : undefined}
                      fill={"fill" in parte ? parte.fill : undefined}
                    />
                    {w > 36 ? (
                      <text
                        x={inicio + w / 2}
                        y={centro + 4}
                        textAnchor="middle"
                        className="fill-ink text-[11px] font-semibold"
                        style={HALO}
                      >
                        {formatarPercentagem(parte.valor, 0)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              <text x={x1 + 10} y={centro + 1} className="fill-ink text-[12.5px] font-semibold">
                {largura < 480 ? novos : t("votoAntecipado.graficos.novosValor", { valor: novos })}
              </text>
              {base && daBase ? (
                <text x={x1 + 10} y={centro + 14} className="fill-ink-3 font-mono text-[10.5px]">
                  {t("votoAntecipado.graficos.novosBase", {
                    ano: base.ano,
                    valor: formatarPercentagem(daBase.novos, 0),
                  })}
                </text>
              ) : null}
            </g>
          );
        });
      }}
    </Grafico>
  );
}

/* ---------- Acima ou abaixo do esperado ---------- */

export function BarrasDesvio({
  titulo,
  linhas,
  faixaAtiva,
  aoEscolher,
  intervalos = {},
}: {
  titulo: string;
  linhas: readonly { faixa: FaixaEtaria; desvio: number | null }[];
  /** Intervalo de cada faixa, desenhado como um traço com hastes por cima da barra. */
  intervalos?: Partial<Record<FaixaEtaria, { min: number; max: number }>>;
  faixaAtiva: FaixaEtaria;
  aoEscolher: (faixa: FaixaEtaria) => void;
}) {
  const alturaLinha = 32;
  const topo = 22;
  const altura = topo + linhas.length * alturaLinha + 4;
  const { maximo: extremo, marcas } = escala(
    Math.max(
      ...linhas.map((l) => Math.abs(l.desvio ?? 0)),
      ...Object.values(intervalos).flatMap((i) => [Math.abs(i.min), Math.abs(i.max)]),
      0.05,
    ),
  );
  // Com muitas marcas, só uma em cada duas, para caberem no telemóvel.
  const positivas = marcas.filter((_, i) => i > 0 && (marcas.length <= 4 || i % 2 === 0));
  return (
    <Grafico titulo={titulo} altura={altura} interativo>
      {(largura) => {
        const x1 = largura - 60;
        const x = (v: number) => ROTULO + ((x1 - ROTULO) * (v + extremo)) / (2 * extremo);
        const zero = x(0);
        return (
          <>
            <Grelha
              valores={[...positivas.map((m) => -m), 0, ...positivas]}
              x={x}
              topo={topo}
              fundo={altura - 2}
              formatar={(v) => (v === 0 ? "0" : formatarVariacao(v))}
            />
            {linhas.map((linha, indice) => {
              const y = topo + indice * alturaLinha;
              const centro = y + alturaLinha / 2;
              const ativa = linha.faixa === faixaAtiva;
              const desvio = linha.desvio;
              const valor = desvio === null ? t("comum.semDados") : formatarVariacao(desvio);
              const intervalo = intervalos[linha.faixa];
              return (
                <g
                  key={linha.faixa}
                  {...linhaEscolhivel(
                    t("votoAntecipado.graficos.linhaFaixa", {
                      faixa: rotuloFaixa(linha.faixa),
                      valor: intervalo
                        ? t("votoAntecipado.graficos.comIntervalo", {
                            valor,
                            de: formatarVariacao(intervalo.min),
                            ate: formatarVariacao(intervalo.max),
                          })
                        : valor,
                    }),
                    () => {
                      aoEscolher(linha.faixa);
                    },
                    ativa,
                  )}
                >
                  <FundoLinha y={y} largura={largura} altura={alturaLinha} ativa={ativa} />
                  <text
                    x={4}
                    y={centro + 4}
                    className={`fill-ink text-[13px] ${ativa ? "font-bold" : "font-medium"}`}
                  >
                    {rotuloFaixa(linha.faixa)}
                  </text>
                  {desvio === null ? null : (
                    <rect
                      x={Math.min(zero, x(desvio))}
                      y={centro - 6}
                      width={Math.abs(x(desvio) - zero)}
                      height={12}
                      rx={1}
                      className={desvio >= 0 ? "fill-up" : "fill-down"}
                    />
                  )}
                  {intervalo ? (
                    <g className="stroke-ink" strokeWidth={1.5}>
                      <line x1={x(intervalo.min)} x2={x(intervalo.max)} y1={centro} y2={centro} />
                      <line
                        x1={x(intervalo.min)}
                        x2={x(intervalo.min)}
                        y1={centro - 5}
                        y2={centro + 5}
                      />
                      <line
                        x1={x(intervalo.max)}
                        x2={x(intervalo.max)}
                        y1={centro - 5}
                        y2={centro + 5}
                      />
                    </g>
                  ) : null}
                  <text
                    x={largura - 4}
                    y={centro + 4}
                    textAnchor="end"
                    className="fill-ink text-[12.5px] font-semibold"
                  >
                    {valor}
                  </text>
                </g>
              );
            })}
          </>
        );
      }}
    </Grafico>
  );
}

/* ---------- Decomposição da variação da quota ---------- */

export function Decomposicao({
  titulo,
  recenseamento,
  participacao,
}: {
  titulo: string;
  recenseamento: number;
  participacao: number;
}) {
  const altura = 200;
  const margemEsquerda = 46;
  const margemFundo = 40;
  const margemTopo = 20;
  const total = recenseamento + participacao;
  const partes = [
    { nome: t("votoAntecipado.decomposicao.recenseamento"), de: 0, ate: recenseamento },
    {
      nome: t("votoAntecipado.decomposicao.participacao"),
      de: recenseamento,
      ate: total,
    },
    { nome: t("votoAntecipado.decomposicao.total"), de: 0, ate: total, total: true },
  ];
  const valores = partes.flatMap((p) => [p.de, p.ate]);
  const negativo = Math.min(...valores) < 0;
  const positivo = Math.max(...valores) > 0;
  const { maximo: extremo, marcas } = escala(Math.max(...valores.map(Math.abs), 0.001));
  const minimo = negativo ? -extremo : 0;
  const maximo = positivo ? extremo : 0;
  const y = (v: number) =>
    margemTopo + ((altura - margemTopo - margemFundo) * (maximo - v)) / (maximo - minimo || 1);
  const passos = [
    ...(negativo ? marcas.slice(1).map((m) => -m) : []),
    0,
    ...(positivo ? marcas.slice(1) : []),
  ];
  const decimaisEixo = casasMarcas(marcas);
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const colunas = (largura - margemEsquerda) / partes.length;
        return (
          <>
            <g aria-hidden="true">
              {passos.map((v) => (
                <g key={v}>
                  <line
                    x1={margemEsquerda}
                    x2={largura}
                    y1={y(v)}
                    y2={y(v)}
                    className={v === 0 ? "stroke-ink-3" : "stroke-rule-2"}
                  />
                  <text x={margemEsquerda - 6} y={y(v) + 4} textAnchor="end" className={TEXTO_EIXO}>
                    {v === 0 ? "0" : formatarPontos(v, decimaisEixo).replace(" pp", "")}
                  </text>
                </g>
              ))}
            </g>
            {partes.map((parte, i) => {
              const x = margemEsquerda + i * colunas + colunas * 0.18;
              const w = colunas * 0.64;
              const variacao = parte.ate - parte.de;
              const cimo = y(Math.max(parte.de, parte.ate));
              return (
                <g key={parte.nome}>
                  <rect
                    x={x}
                    y={cimo}
                    width={w}
                    height={Math.max(1, Math.abs(y(parte.de) - y(parte.ate)))}
                    rx={1}
                    className={
                      parte.total ? "fill-signal" : variacao >= 0 ? "fill-up" : "fill-down"
                    }
                  />
                  {i < partes.length - 1 ? (
                    <line
                      x1={x + w}
                      x2={x + colunas}
                      y1={y(parte.ate)}
                      y2={y(parte.ate)}
                      strokeDasharray="2 2"
                      className="stroke-ink-3"
                    />
                  ) : null}
                  <text
                    x={x + w / 2}
                    y={cimo - 6}
                    textAnchor="middle"
                    className="fill-ink text-[11.5px] font-semibold"
                  >
                    {formatarPontos(variacao, 2)}
                  </text>
                  <text
                    x={x + w / 2}
                    y={altura - margemFundo + 20}
                    textAnchor="middle"
                    className={`${largura < 420 ? "text-[10.5px]" : "text-[12px]"} ${
                      parte.total ? "fill-ink font-semibold" : "fill-ink-2"
                    }`}
                  >
                    {parte.nome}
                  </text>
                </g>
              );
            })}
          </>
        );
      }}
    </Grafico>
  );
}

/* ---------- Curva da coorte ---------- */

export function CurvaCoorte({
  titulo,
  curvas,
  anoAtual,
  diasAntes,
  comparacoes,
  diaInicial,
  formato = "percentagem",
}: {
  titulo: string;
  curvas: readonly CurvaAno[];
  anoAtual: number;
  diasAntes: number;
  comparacoes: readonly AnoComparado[];
  /** Primeiro dia (mais afastado da eleição) e último dia mostrados. */
  diaInicial: { de: number; ate: number };
  /** Percentagem (taxas) ou número de votos (estados sem ficheiro de eleitores). */
  formato?: "percentagem" | "numero";
}) {
  const altura = 240;
  const margem = { esquerda: 44, direita: 54, topo: 14, fundo: 28 };
  const { de, ate } = diaInicial;
  const visiveis = curvas.map((curva) => ({
    ...curva,
    pontos: curva.pontos.filter((p) => p.dias <= de && p.dias >= ate),
  }));
  const { maximo, marcas: marcasY } = escala(
    Math.max(...visiveis.flatMap((c) => c.pontos.map((p) => p.taxa)), 0.001),
  );
  const decimais = casasMarcas(marcasY);
  const eixo = (v: number) =>
    formato === "numero" ? formatarCompacto(v) : formatarPercentagem(v, decimais);
  const ponta = (v: number) =>
    formato === "numero" ? formatarCompacto(v) : formatarPercentagem(v, casas(maximo));
  const ordem = [...visiveis].sort((a, b) =>
    a.ano === anoAtual ? 1 : b.ano === anoAtual ? -1 : a.ano - b.ano,
  );
  // Marcas em múltiplos de 5 ou 10 dias, mais o último dia mostrado.
  const passoDias = de - ate > 30 ? 10 : 5;
  const marcas = [
    ...Array.from({ length: Math.floor(de / passoDias) + 1 }, (_, i) => i * passoDias).filter(
      (d) => d <= de && d - ate >= passoDias * 0.8,
    ),
    ate,
  ];
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const x = (dias: number) =>
          margem.esquerda +
          ((largura - margem.esquerda - margem.direita) * (de - dias)) / Math.max(1, de - ate);
        const y = (v: number) =>
          margem.topo + (altura - margem.topo - margem.fundo) * (1 - v / maximo);
        const anteriores = ordem.filter((c) => c.ano !== anoAtual && c.pontos.length > 0);
        const posicoesRotulos = afastarRotulos(
          anteriores.map((c) => y(c.pontos.at(-1)?.taxa ?? 0) + 4),
        );
        const rotuloDe = (ano: number) =>
          posicoesRotulos[anteriores.findIndex((c) => c.ano === ano)] ?? 0;
        return (
          <>
            <g aria-hidden="true">
              {marcasY.map((v) => (
                <g key={v}>
                  <line
                    x1={margem.esquerda}
                    x2={largura - margem.direita}
                    y1={y(v)}
                    y2={y(v)}
                    className="stroke-rule-2"
                  />
                  <text
                    x={margem.esquerda - 6}
                    y={y(v) + 4}
                    textAnchor="end"
                    className={TEXTO_EIXO}
                  >
                    {eixo(v)}
                  </text>
                </g>
              ))}
              {[...new Set(marcas)].map((d) => (
                <text key={d} x={x(d)} y={altura - 8} textAnchor="middle" className={TEXTO_EIXO}>
                  {formatarDiaCiclo(d)}
                </text>
              ))}
              {diasAntes >= ate && diasAntes <= de ? (
                <line
                  x1={x(diasAntes)}
                  x2={x(diasAntes)}
                  y1={margem.topo}
                  y2={altura - margem.fundo}
                  strokeDasharray="2 3"
                  className="stroke-signal"
                />
              ) : null}
            </g>
            {ordem.map((curva) => {
              const ultimo = curva.pontos.at(-1);
              if (!ultimo) return null;
              const estilo = estiloAno(curva.ano, anoAtual, comparacoes);
              const caminho = curva.pontos
                .map((p, i) => `${i ? "L" : "M"}${x(p.dias).toFixed(1)},${y(p.taxa).toFixed(1)}`)
                .join("");
              const atual = curva.ano === anoAtual;
              return (
                <g key={curva.ano}>
                  <path
                    d={caminho}
                    fill="none"
                    strokeWidth={estilo.largura}
                    strokeDasharray={estilo.tracejado}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    className={estilo.classe}
                  />
                  {atual ? (
                    <>
                      <circle
                        cx={x(ultimo.dias)}
                        cy={y(ultimo.taxa)}
                        r={4.5}
                        strokeWidth={2}
                        className="fill-signal stroke-sheet"
                      />
                      <text
                        x={x(ultimo.dias) + 8}
                        y={y(ultimo.taxa) - 8}
                        className="fill-ink text-[12.5px] font-bold"
                        style={HALO}
                      >
                        {ponta(ultimo.taxa)}
                      </text>
                    </>
                  ) : (
                    <text
                      x={Math.min(x(ultimo.dias) + 6, largura - margem.direita + 6)}
                      y={rotuloDe(curva.ano)}
                      className={TEXTO_EIXO}
                    >
                      {curva.ano}
                    </text>
                  )}
                </g>
              );
            })}
          </>
        );
      }}
    </Grafico>
  );
}

/* ---------- Idade × partido ou modalidade ---------- */

export function Cruzamento<F extends FaixaAgregada = FaixaEtaria>({
  titulo,
  linhas,
  modo,
  faixaAtiva,
  aoEscolher,
}: {
  titulo: string;
  linhas: readonly CruzamentoFaixa<F>[];
  modo: "partido" | "modalidade";
  /** Faixa em foco; sem ela (e sem `aoEscolher`) o gráfico é só de leitura. */
  faixaAtiva?: F;
  aoEscolher?: (faixa: F) => void;
}) {
  const alturaLinha = 30;
  const topo = 6;
  const altura = topo + linhas.length * alturaLinha + 4;
  return (
    <Grafico titulo={titulo} altura={altura} interativo={aoEscolher !== undefined}>
      {(largura) => {
        const x1 = largura - (largura < 480 ? 84 : 104);
        const util = x1 - ROTULO;
        return linhas.map((linha, indice) => {
          const y = topo + indice * alturaLinha;
          const centro = y + alturaLinha / 2;
          const ativa = linha.faixa === faixaAtiva;
          let x = ROTULO;
          const resumo =
            modo === "partido"
              ? PARTIDOS.map(
                  (p) =>
                    `${t(`votoAntecipado.partidos.${p}`)} ${formatarPercentagem(linha.partidos[p], 0)}`,
                ).join(", ")
              : t("votoAntecipado.graficos.correioValor", {
                  valor: formatarPercentagem(linha.correio ?? 0, 0),
                });
          return (
            <g
              key={linha.faixa}
              {...linhaEscolhivel(
                modo === "partido" && linha.variacaoDemRep !== null
                  ? t("votoAntecipado.graficos.linhaDemRep", {
                      linha: t("votoAntecipado.graficos.linhaFaixa", {
                        faixa: rotuloFaixa(linha.faixa),
                        valor: resumo,
                      }),
                      valor: formatarPontos(linha.variacaoDemRep, 0).replace(" pp", ""),
                    })
                  : t("votoAntecipado.graficos.linhaFaixa", {
                      faixa: rotuloFaixa(linha.faixa),
                      valor: resumo,
                    }),
                aoEscolher
                  ? () => {
                      aoEscolher(linha.faixa);
                    }
                  : undefined,
                ativa,
              )}
            >
              <FundoLinha y={y} largura={largura} altura={alturaLinha} ativa={ativa} />
              <text
                x={4}
                y={centro + 4}
                className={`fill-ink text-[13px] ${ativa ? "font-bold" : "font-medium"}`}
              >
                {rotuloFaixa(linha.faixa)}
              </text>
              {modo === "partido" ? (
                <>
                  {PARTIDOS.map((partido) => {
                    const w = util * linha.partidos[partido];
                    const inicio = x;
                    x += w;
                    return (
                      <g key={partido}>
                        <RetanguloPartido
                          partido={partido}
                          x={inicio}
                          y={centro - 8}
                          width={Math.max(0, w - 1)}
                          height={16}
                        />
                        {w > 30 && partido !== "outro" ? (
                          <text
                            x={inicio + w / 2}
                            y={centro + 4}
                            textAnchor="middle"
                            className="fill-ink text-[11px] font-semibold"
                            style={HALO}
                          >
                            {Math.round(linha.partidos[partido] * 100)}
                          </text>
                        ) : null}
                      </g>
                    );
                  })}
                  {linha.variacaoDemRep === null ? null : (
                    <text x={x1 + 8} y={centro + 4} className="fill-ink-2 font-mono text-[11px]">
                      {t("votoAntecipado.graficos.demRep", {
                        valor: formatarPontos(linha.variacaoDemRep, 0).replace(" pp", ""),
                      })}
                    </text>
                  )}
                </>
              ) : (
                <>
                  <rect
                    x={ROTULO}
                    y={centro - 8}
                    width={Math.max(0, util * (linha.correio ?? 0) - 1)}
                    height={16}
                    className="fill-ink-2"
                  />
                  <rect
                    x={ROTULO + util * (linha.correio ?? 0)}
                    y={centro - 8}
                    width={util * (1 - (linha.correio ?? 0))}
                    height={16}
                    className="fill-ink-3 opacity-30"
                  />
                  <text x={x1 + 8} y={centro + 4} className="fill-ink-2 font-mono text-[11px]">
                    {t("votoAntecipado.graficos.correioValor", {
                      valor: formatarPercentagem(linha.correio ?? 0, 0),
                    })}
                  </text>
                </>
              )}
            </g>
          );
        });
      }}
    </Grafico>
  );
}

/* ---------- Reserva restante ---------- */

export function BarrasReserva({
  titulo,
  partidos,
  anoAtual,
  comparacoes,
  anoBase,
  detalhes,
}: {
  titulo: string;
  partidos: readonly ReservaPartido[];
  anoAtual: number;
  comparacoes: readonly AnoComparado[];
  anoBase: number | null;
  /** Texto por baixo de cada barra; por omissão, os habituais que faltam votar. */
  detalhes?: readonly string[];
}) {
  const alturaLinha = 44;
  const topo = 22;
  const altura = topo + partidos.length * alturaLinha + 4;
  const { maximo, marcas } = escala(
    Math.max(...partidos.flatMap((p) => [p.mobilizacao ?? 0, p.mobilizacaoBase ?? 0]), 0.001),
  );
  const decimais = casas(maximo);
  const estiloBase = anoBase === null ? null : estiloAno(anoBase, anoAtual, comparacoes);
  return (
    <Grafico titulo={titulo} altura={altura}>
      {(largura) => {
        const rotulo = largura < 480 ? 92 : 112;
        const x1 = largura - (largura < 480 ? 72 : 92);
        const x = (v: number) => rotulo + ((x1 - rotulo) * v) / maximo;
        return (
          <>
            <Grelha
              valores={
                largura < 480 && marcas.length > 4 ? marcas.filter((_, i) => i % 2 === 0) : marcas
              }
              x={x}
              topo={topo}
              fundo={altura - 2}
              formatar={(v) => formatarPercentagem(v, casasMarcas(marcas))}
            />
            {partidos.map((p, indice) => {
              const y = topo + indice * alturaLinha;
              const centro = y + alturaLinha / 2 - 4;
              return (
                <g key={p.partido}>
                  <text x={4} y={centro + 4} className="fill-ink text-[13px] font-medium">
                    {t(`votoAntecipado.partidos.${p.partido}`)}
                  </text>
                  <RetanguloPartido
                    partido={p.partido}
                    x={rotulo}
                    y={centro - 7}
                    width={Math.max(0, x(p.mobilizacao ?? 0) - rotulo)}
                    height={14}
                  />
                  {p.mobilizacaoBase !== null && estiloBase ? (
                    <line
                      x1={x(p.mobilizacaoBase)}
                      x2={x(p.mobilizacaoBase)}
                      y1={centro - 11}
                      y2={centro + 11}
                      strokeWidth={2}
                      strokeDasharray={estiloBase.tracejado ? "3 2" : undefined}
                      className={estiloBase.classe}
                    />
                  ) : null}
                  <text x={x1 + 8} y={centro + 4} className="fill-ink text-[13px] font-semibold">
                    {formatarPercentagem(p.mobilizacao ?? 0, decimais)}
                  </text>
                  <text x={rotulo} y={centro + 22} className="fill-ink-3 font-mono text-[10.5px]">
                    {detalhes?.[indice] ??
                      t("votoAntecipado.reserva.restantes", {
                        valor: formatarNumero(p.restantes),
                      })}
                  </text>
                </g>
              );
            })}
          </>
        );
      }}
    </Grafico>
  );
}
