import Link from "next/link";
import { Painel } from "@/components/ui/Painel.tsx";
import { nomeEstado } from "@/lib/estados.ts";
import { FONTE_FECHO, gruposFecho } from "@/lib/fecho.ts";
import { formatarHora, formatarPercentagem } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import { categoria, type CorridaVista, type VistaPrevisao } from "@/lib/previsao/vista.ts";
import { ContagemFecho } from "./ContagemFecho.tsx";

function lisboa(instante: string): string {
  return formatarHora(new Date(instante), "Europe/Lisbon");
}

function naoSolida(c: CorridaVista): boolean {
  const cat = categoria(c.probD);
  return c.decidida === null && cat !== "solidaD" && cat !== "solidaR";
}

/** Corrida ao Senado com o favorito da previsão, por exemplo "Senado: D 55%". */
function senado(c: CorridaVista): string {
  const lado = c.probD >= 0.5 ? "D" : "R";
  return t(c.especial ? "fecho.senadoEspecial" : "fecho.senado", {
    favorito: `${lado} ${formatarPercentagem(lado === "D" ? c.probD : 1 - c.probD, 0)}`,
  });
}

/**
 * Horários de fecho das urnas na noite eleitoral, em hora de Lisboa, com as corridas a
 * seguir em cada estado (Senado e distritos que a previsão não dá como sólidos).
 */
export function HorariosFecho({ previsao }: { previsao: VistaPrevisao | null }) {
  const grupos = gruposFecho();
  const corridas = previsao ? [...previsao.corridasSenado, ...previsao.corridasCamara] : [];
  const notas = (estado: string) => {
    const doEstado = corridas.filter((c) => c.estado === estado);
    const partes = doEstado.filter((c) => c.camara === "senado").map(senado);
    const camara = doEstado.filter((c) => c.camara === "camara" && naoSolida(c)).length;
    if (camara > 0) {
      partes.push(t(camara === 1 ? "fecho.distrito" : "fecho.distritos", { n: camara }));
    }
    return partes.join(" · ");
  };
  return (
    <Painel
      sobrelinha={t("fecho.sobrelinha")}
      titulo={t("fecho.titulo")}
      descricao={t("fecho.texto")}
      fontes={[FONTE_FECHO]}
      metodo={t("fecho.metodo")}
    >
      <ContagemFecho grupos={grupos} />
      <ol className="flex flex-col">
        {grupos.map((g) => (
          <li
            key={g.instante}
            className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 border-t border-rule-2 py-2 text-sm"
          >
            <span className="font-mono text-[15px] font-semibold">{lisboa(g.instante)}</span>
            <ul className="flex flex-col gap-1">
              {g.estados.map((f) => {
                const extra = notas(f.estado);
                return (
                  <li key={f.estado}>
                    <span className="font-semibold">{nomeEstado(f.estado)}</span>
                    {f.todas ? (
                      <span className="text-ink-3">
                        {" "}
                        {t("fecho.todas", { hora: lisboa(f.todas) })}
                      </span>
                    ) : null}
                    {f.confirmar ? (
                      <span className="text-ink-3"> {t("fecho.confirmar")}</span>
                    ) : null}
                    {extra ? <span className="block text-[12.5px] text-ink-2">{extra}</span> : null}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ol>
      {previsao ? (
        <p className="text-sm">
          <Link
            href="/resultados/guia/"
            prefetch={false}
            className="text-ink underline decoration-rule underline-offset-[3px]"
          >
            {t("guia.ligacao")}
          </Link>
        </p>
      ) : null}
    </Painel>
  );
}
