/**
 * Metadados de cada página: título, descrição, endereço canónico e cartões para
 * redes sociais (Open Graph e Twitter). O Next substitui o objeto openGraph inteiro
 * quando uma página o define, por isso cada página recebe o conjunto completo.
 */

import type { Metadata } from "next";
import { TAMANHO_CARTAO } from "./cartao-tamanho.ts";
import { t } from "./mensagens.ts";

export function metadadosPagina({
  titulo,
  descricao,
  caminho,
  cartao,
}: {
  /** Título da página; `null` na página inicial, que usa o título do site. */
  titulo: string | null;
  descricao: string;
  /** Caminho com barra final, por exemplo "/previsao/"; `null` no layout (sem canónico). */
  caminho: string | null;
  /** Nome do cartão em /cartoes/ (ex.: "previsao.png"). */
  cartao: string;
}): Metadata {
  const tituloCompleto = titulo
    ? `${titulo} · ${t("site.nome")}`
    : `${t("site.nome")} · ${t("site.subtitulo")}`;
  const imagem = {
    url: `/cartoes/${cartao}`,
    ...TAMANHO_CARTAO,
    alt: tituloCompleto,
    type: "image/png",
  };
  return {
    ...(titulo ? { title: titulo } : {}),
    description: descricao,
    ...(caminho === null ? {} : { alternates: { canonical: caminho } }),
    openGraph: {
      type: "website",
      locale: "pt_PT",
      siteName: t("site.nome"),
      title: tituloCompleto,
      description: descricao,
      ...(caminho === null ? {} : { url: caminho }),
      images: [imagem],
    },
    twitter: {
      card: "summary_large_image",
      title: tituloCompleto,
      description: descricao,
      images: [imagem],
    },
  };
}
