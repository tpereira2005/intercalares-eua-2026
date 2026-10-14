import type { Metadata } from "next";
import { PaginaDemografia } from "@/components/demografia/PaginaDemografia.tsx";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { demografiaTodos } from "@/lib/demografia.ts";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarTodas } from "@/lib/voto-antecipado/carregar.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.demografia.titulo"),
  descricao: t("seccoes.demografia.descricao"),
  caminho: "/demografia/",
  cartao: "voto-antecipado.png",
});

export default function Pagina() {
  const todas = carregarTodas();
  const estados = demografiaTodos(todas);
  if (estados.length === 0) {
    return (
      <SeccaoEmPreparacao
        titulo={t("seccoes.demografia.titulo")}
        descricao={t("seccoes.demografia.descricao")}
      />
    );
  }
  const comIdade = new Set(estados.map((e) => e.estado));
  const fontes = [...todas.individuais, ...todas.agregados]
    .filter((v) => comIdade.has(v.estado))
    .flatMap((v) => v.fontes)
    .filter((f, i, lista) => lista.findIndex((g) => g.nome === f.nome) === i);
  const recente = [...estados].sort((a, b) => b.dadosAte.localeCompare(a.dadosAte))[0];
  return (
    <PaginaDemografia
      estados={estados}
      fontes={fontes}
      dadosAte={recente ? { data: recente.dadosAte, dias: recente.diasAntes } : null}
    />
  );
}
