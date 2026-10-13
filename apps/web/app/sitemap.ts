import type { MetadataRoute } from "next";
import { PAGINAS_FIXAS, URL_SITE } from "@/lib/site.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

export const dynamic = "force-static";

/** Páginas públicas, incluindo uma por estado com dados do voto antecipado. */
export default function sitemap(): MetadataRoute.Sitemap {
  const estados = resumirTodos(carregarTodas()).map(
    (r) => `/voto-antecipado/${r.estado.toLowerCase()}/`,
  );
  return [...PAGINAS_FIXAS, ...estados].map((caminho) => ({
    url: new URL(caminho, URL_SITE).toString(),
  }));
}
