import Link from "next/link";
import { Painel } from "@/components/ui/Painel.tsx";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import { nomeEstado } from "@/lib/estados.ts";
import { formatarMargemPontos, formatarNumero } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { DadosPrevisao } from "@/lib/previsao/carregar.ts";
import type { VistaCenarios } from "@/lib/previsao/explorador.ts";
import { ExploradorCenarios } from "./ExploradorCenarios.tsx";
import { Estimativa, VersaoPrevisao } from "./PaginaPrevisao.tsx";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

/** Página do explorador de cenários: /previsao/cenarios/. */
export function PaginaCenarios({
  dados,
  cenarios,
}: {
  dados: DadosPrevisao;
  cenarios: VistaCenarios;
}) {
  const vista = dados.previsao;
  const corridas = vista.corridasSenado.map((c) => {
    const estado = nomeEstado(c.estado);
    return {
      id: c.id,
      nome: c.especial ? t("previsao.caminho.especial", { estado }) : estado,
      href: caminhoPaginaCorrida(c.id),
    };
  });
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="rotulo mb-1">{t("previsao.sobrelinha", { ano: vista.ano })}</p>
          <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
            {t("previsao.cenarios.titulo")}
          </h1>
          <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
            {t("previsao.cenarios.lede", {
              ambiente: formatarMargemPontos(cenarios.ambienteBase),
            })}
          </p>
        </div>
        <VersaoPrevisao vista={vista} />
      </header>

      <Painel
        sobrelinha={t("previsao.cenarios.sobrelinha")}
        titulo={t("previsao.cenarios.painelTitulo")}
        descricao={t("previsao.cenarios.texto")}
        acessorio={<Estimativa />}
        fontes={cenarios.fontes}
        metodo={t("previsao.cenarios.metodo", {
          simulacoes: formatarNumero(cenarios.simulacoes),
          desvio: cenarios.desvioPadraoAmbiente.toLocaleString("pt-PT", {
            maximumFractionDigits: 1,
          }),
        })}
      >
        <ExploradorCenarios
          vista={cenarios}
          corridas={corridas}
          maiorias={{ camara: vista.camara.maioria, senado: vista.senado.maioria }}
        />
      </Painel>

      <p className="text-sm">
        <Link href="/previsao/" className={LIGACAO}>
          {t("previsao.paginas.voltar")}
        </Link>
      </p>
    </div>
  );
}
