import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { t } from "@/lib/mensagens.ts";

export const metadata: Metadata = { title: t("seccoes.previsao.titulo") };

export default function Pagina() {
  return (
    <SeccaoEmPreparacao
      titulo={t("seccoes.previsao.titulo")}
      descricao={t("seccoes.previsao.descricao")}
    />
  );
}
