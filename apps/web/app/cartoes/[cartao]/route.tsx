import { cartao, type ConteudoCartao } from "@/lib/cartao.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import {
  DIA_DA_ELEICAO,
  formatarCompacto,
  formatarData,
  formatarNumero,
  formatarPercentagem,
} from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import type { ResumoVista } from "@/lib/previsao/vista.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

/**
 * Cartões para redes sociais, gerados no build como /cartoes/<nome>.png (com
 * extensão, para o servidor de ficheiros estáticos indicar image/png).
 */

export const dynamic = "force-static";
export const dynamicParams = false;

function data(dia: string): Date {
  return new Date(`${dia}T12:00:00Z`);
}

function seccao(chave: "mapa" | "metodologia" | "sondagens" | "votoAntecipado"): ConteudoCartao {
  return {
    sobrelinha: formatarData(DIA_DA_ELEICAO),
    titulo: t(`seccoes.${chave}.titulo`),
    texto: t(`seccoes.${chave}.descricao`),
  };
}

function lider(r: ResumoVista): string {
  return r.probD >= r.probR
    ? `D ${formatarPercentagem(r.probD, 0)}`
    : `R ${formatarPercentagem(r.probR, 0)}`;
}

function conteudos(): Map<string, ConteudoCartao> {
  const lista = new Map<string, ConteudoCartao>();
  lista.set("inicio.png", {
    sobrelinha: formatarData(DIA_DA_ELEICAO),
    titulo: t("cartoes.inicio.titulo"),
    texto: t("cartoes.inicio.texto"),
  });
  lista.set("mapa.png", seccao("mapa"));
  lista.set("metodologia.png", seccao("metodologia"));
  lista.set("voto-antecipado.png", seccao("votoAntecipado"));
  lista.set("sondagens.png", seccao("sondagens"));
  lista.set("resultados.png", {
    sobrelinha: formatarData(DIA_DA_ELEICAO),
    titulo: t("cartoes.resultados.titulo"),
    texto: t("cartoes.resultados.texto"),
  });

  const previsao = carregarPrevisao()?.previsao;
  lista.set(
    "previsao.png",
    previsao
      ? {
          sobrelinha: t("cartoes.previsao.sobrelinha", {
            data: formatarData(data(previsao.corte)),
          }),
          titulo: t("cartoes.previsao.titulo"),
          destaque: t("cartoes.previsao.destaque", {
            camara: lider(previsao.camara),
            senado: lider(previsao.senado),
          }),
          texto: t("cartoes.previsao.texto", { simulacoes: formatarNumero(previsao.simulacoes) }),
        }
      : {
          sobrelinha: formatarData(DIA_DA_ELEICAO),
          titulo: t("seccoes.previsao.titulo"),
          texto: t("seccoes.previsao.descricao"),
        },
  );

  for (const r of resumirTodos(carregarTodas())) {
    const votos = formatarCompacto(r.votos);
    lista.set(`voto-antecipado-${r.estado.toLowerCase()}.png`, {
      sobrelinha: t("cartoes.votoAntecipado.sobrelinha", { estado: nomeEstado(r.estado) }),
      titulo: t("cartoes.votoAntecipado.titulo"),
      destaque:
        r.quota65 === null
          ? t("cartoes.votoAntecipado.destaqueSemIdade", { votos })
          : t("cartoes.votoAntecipado.destaque", { votos, quota: formatarPercentagem(r.quota65) }),
      texto: t("cartoes.votoAntecipado.dadosAte", { data: formatarData(data(r.dadosAte)) }),
    });
  }
  return lista;
}

export function generateStaticParams(): { cartao: string }[] {
  return [...conteudos().keys()].map((cartao) => ({ cartao }));
}

export async function GET(_pedido: Request, { params }: { params: Promise<{ cartao: string }> }) {
  const conteudo = conteudos().get((await params).cartao);
  if (!conteudo) return new Response(null, { status: 404 });
  return cartao(conteudo);
}
