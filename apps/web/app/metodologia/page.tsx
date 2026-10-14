import type { Metadata } from "next";
import { IndiceMetodologia } from "@/components/metodologia/PaginasMetodologia.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { DOCUMENTOS, lerDocumento } from "@/lib/metodologia.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.metodologia.titulo"),
  descricao: t("seccoes.metodologia.descricao"),
  caminho: "/metodologia/",
  cartao: "metodologia.png",
});

export default function Pagina() {
  const documentos = DOCUMENTOS.flatMap((d) => {
    const lido = lerDocumento(d, t("metodologia.tabela"), t("metodologia.blocoCodigo"));
    return lido ? [lido] : [];
  });
  return <IndiceMetodologia documentos={documentos} />;
}
