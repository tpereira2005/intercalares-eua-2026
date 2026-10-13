"use client";

import { linhasPorIdade } from "@/components/voto-antecipado/anos.ts";
import { BarrasIdade } from "@/components/voto-antecipado/graficos.tsx";
import { AmostraAno, ItemLegenda, Legenda } from "@/components/voto-antecipado/legendas.tsx";
import { t } from "@/lib/mensagens.ts";
import type { VistaVotoAntecipado } from "@/lib/voto-antecipado/vista.ts";

/** Composição do voto antecipado por idade, só de leitura, para o painel inicial. */
export function QuemVotou({ vista }: { vista: VistaVotoAntecipado }) {
  const comparacao = vista.comparacoes[0];
  if (!comparacao) return null;
  return (
    <>
      <Legenda>
        <ItemLegenda amostra={<AmostraAno ano={vista.ano} anoAtual={vista.ano} vista={vista} />}>
          {vista.ano}
        </ItemLegenda>
        {vista.comparacoes.map((c) => (
          <ItemLegenda
            key={c.anoBase}
            amostra={<AmostraAno ano={c.anoBase} anoAtual={vista.ano} vista={vista} />}
          >
            {t("votoAntecipado.legenda.mesmoDia", { ano: c.anoBase })}
          </ItemLegenda>
        ))}
      </Legenda>
      <BarrasIdade
        titulo={t("votoAntecipado.graficos.composicaoAria", { ano: vista.ano })}
        linhas={linhasPorIdade(vista, comparacao, "quota")}
        anoAtual={vista.ano}
        anoComparar={comparacao.anoBase}
        comparacoes={vista.comparacoes}
        compacto
      />
    </>
  );
}
