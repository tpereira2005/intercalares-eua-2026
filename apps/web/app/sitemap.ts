import type { MetadataRoute } from "next";
import { caminhoPaginaCorrida, todasCorridas } from "@/lib/corridas.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import { PAGINAS_FIXAS, URL_SITE } from "@/lib/site.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

export const dynamic = "force-static";

/** Páginas públicas, incluindo uma por estado com dados do voto antecipado e uma por corrida. */
export default function sitemap(): MetadataRoute.Sitemap {
  const estados = resumirTodos(carregarTodas()).map(
    (r) => `/voto-antecipado/${r.estado.toLowerCase()}/`,
  );
  const previsao = carregarPrevisao()?.previsao;
  const corridas = previsao ? todasCorridas(previsao).map((c) => caminhoPaginaCorrida(c.id)) : [];
  return [...PAGINAS_FIXAS, ...estados, ...corridas].map((caminho) => ({
    url: new URL(caminho, URL_SITE).toString(),
  }));
}
