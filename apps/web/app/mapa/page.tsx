import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { t } from "@/lib/mensagens.ts";

export const metadata: Metadata = { title: t("seccoes.mapa.titulo") };

export default function Pagina() {
  return (
    <SeccaoEmPreparacao titulo={t("seccoes.mapa.titulo")} descricao={t("seccoes.mapa.descricao")} />
  );
}
