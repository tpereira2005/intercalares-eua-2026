import type { Metadata } from "next";
import { PaginaCorrida } from "@/components/corridas/PaginaCorrida.tsx";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { encontrarCorrida, todasCorridas, tituloCorrida } from "@/lib/corridas.ts";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import { carregarSondagens } from "@/lib/sondagens/carregar.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

export const dynamicParams = false;

/** Uma página por corrida da previsão; sem ficheiro, só a da Carolina do Norte, em preparação. */
export function generateStaticParams(): { corrida: string }[] {
  const previsao = carregarPrevisao()?.previsao;
  const corridas = previsao ? todasCorridas(previsao) : [];
  return corridas.length > 0
    ? corridas.map((c) => ({ corrida: c.id.toLowerCase() }))
    : [{ corrida: "nc-s" }];
}

function encontrar(id: string) {
  const dados = carregarPrevisao();
  const corrida = dados ? encontrarCorrida(dados.previsao, id) : null;
  return dados && corrida ? { dados, corrida } : null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ corrida: string }>;
}): Promise<Metadata> {
  const id = (await params).corrida;
  const encontrada = encontrar(id);
  return metadadosPagina({
    titulo: encontrada ? tituloCorrida(encontrada.corrida) : t("seccoes.previsao.titulo"),
    descricao: encontrada
      ? t("corrida.metadados", { corrida: tituloCorrida(encontrada.corrida) })
      : t("seccoes.previsao.descricao"),
    caminho: `/corridas/${id}/`,
    cartao: "previsao.png",
  });
}

export default async function Pagina({ params }: { params: Promise<{ corrida: string }> }) {
  const encontrada = encontrar((await params).corrida);
  if (!encontrada) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.previsao.titulo")}
        descricao={t("seccoes.previsao.descricao")}
      />
    );
  }
  const { dados, corrida } = encontrada;
  const sondagens = carregarSondagens()?.corridas ?? [];
  const estadosVotoAntecipado = resumirTodos(carregarTodas()).map((r) => r.estado);
  return (
    <PaginaCorrida
      corrida={corrida}
      vista={dados.previsao}
      evolucao={dados.evolucao?.corridas.get(corrida.id) ?? []}
      comSondagens={sondagens.some((s) => s.id === corrida.id)}
      comVotoAntecipado={estadosVotoAntecipado.includes(corrida.estado)}
    />
  );
}
