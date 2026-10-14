import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PaginaDocumento } from "@/components/metodologia/PaginasMetodologia.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { DOCUMENTOS, caminhoMetodologia, lerDocumento, type Documento } from "@/lib/metodologia.ts";

export const dynamicParams = false;

export function generateStaticParams(): { documento: Documento }[] {
  return DOCUMENTOS.map((documento) => ({ documento }));
}

interface Parametros {
  params: Promise<{ documento: Documento }>;
}

export async function generateMetadata({ params }: Parametros): Promise<Metadata> {
  const { documento } = await params;
  const lido = lerDocumento(documento, t("metodologia.tabela"));
  return metadadosPagina({
    titulo: lido?.titulo ?? t("seccoes.metodologia.titulo"),
    descricao: lido?.resumo.slice(0, 200) ?? t("seccoes.metodologia.descricao"),
    caminho: caminhoMetodologia(documento),
    cartao: "metodologia.png",
  });
}

export default async function Pagina({ params }: Parametros) {
  const { documento } = await params;
  const lido = lerDocumento(documento, t("metodologia.tabela"));
  if (!lido) notFound();
  return <PaginaDocumento documento={lido} />;
}
