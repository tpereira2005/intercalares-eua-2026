import type { Metadata } from "next";
import { SeccaoEmPreparacao } from "@/components/layout/SeccaoEmPreparacao.tsx";
import { HorariosFecho } from "@/components/noite/HorariosFecho.tsx";
import { ResultadosAoVivo } from "@/components/resultados/ResultadosAoVivo.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarResultados } from "@/lib/resultados/carregar.ts";
import { previsaoParaResultados } from "@/lib/resultados/vista.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.resultados.titulo"),
  descricao: t("seccoes.resultados.descricao"),
  caminho: "/resultados/",
  cartao: "resultados.png",
});

export default function Pagina() {
  // Lidos e validados no build; durante a noite, o browser vai buscar dados mais recentes
  // à API do Worker. Sem contagem nem projeção, a página fica em preparação.
  const previsao = carregarPrevisao()?.previsao ?? null;
  return (
    <>
      <ResultadosAoVivo
        inicial={carregarResultados()}
        previsao={previsao ? previsaoParaResultados(previsao) : null}
        emPreparacao={
          <SeccaoEmPreparacao
            titulo={t("seccoes.resultados.titulo")}
            descricao={t("seccoes.resultados.descricao")}
          />
        }
      />
      <HorariosFecho previsao={previsao} />
    </>
  );
}
