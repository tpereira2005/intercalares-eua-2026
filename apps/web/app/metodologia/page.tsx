import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.metodologia.titulo"),
  descricao: t("seccoes.metodologia.descricao"),
  caminho: "/metodologia/",
  cartao: "metodologia.png",
});

export default function Pagina() {
  return (
    <SeccaoEmPreparacao
      titulo={t("seccoes.metodologia.titulo")}
      descricao={t("seccoes.metodologia.descricao")}
    />
  );
}
