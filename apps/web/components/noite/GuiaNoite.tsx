import Link from "next/link";
import { rotuloPosicao } from "@/components/previsao/PainelPrognosticos.tsx";
import { ESTILO_CATEGORIA, Estimativa } from "@/components/previsao/PaginaPrevisao.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { caminhoPaginaCorrida } from "@/lib/corridas.ts";
import { nomeEstado } from "@/lib/estados.ts";
import { FONTE_FECHO } from "@/lib/fecho.ts";
import { formatarHora, formatarPercentagem } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { CorridaGuia, Decisiva, EstadoGuia, VistaGuia } from "@/lib/noite/guia.ts";
import { corDe, type VistaPrognosticos } from "@/lib/previsao/prognosticos.ts";
import type { Categoria, CorridaVista, Lado } from "@/lib/previsao/vista.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function lisboa(instante: string): string {
  return formatarHora(new Date(instante), "Europe/Lisbon");
}

function Amostra({ cor }: { cor: Categoria }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block size-3 shrink-0 rounded-[2px] ${ESTILO_CATEGORIA[cor].className}`}
      style={ESTILO_CATEGORIA[cor].style}
    />
  );
}

function nomeCorrida(c: CorridaVista): string {
  const estado = nomeEstado(c.estado);
  if (c.camara === "camara") return c.id;
  return c.especial ? t("previsao.caminho.especial", { estado }) : estado;
}

/** "democratas" ou "republicanos". */
function partidos(lado: Lado): string {
  return t(`previsao.partidos.${lado}`).toLowerCase();
}

/** Uma linha por corrida: quando é a decisiva dos dois lados, diz-se uma vez. */
function LinhaDecisiva({ ds }: { ds: readonly Decisiva[] }) {
  const d = ds[0];
  if (!d) return null;
  const texto =
    ds.length > 1
      ? t("guia.decisivas.ambos", { prob: formatarPercentagem(d.corrida.probD, 0) })
      : t("guia.decisivas.linha", {
          prob: formatarPercentagem(d.prob, 0),
          partido: partidos(d.lado),
        });
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-3 border-t border-rule-2 py-1.5">
      <span>
        <Link href={caminhoPaginaCorrida(d.corrida.id)} className={`font-semibold ${LIGACAO}`}>
          {nomeCorrida(d.corrida)}
        </Link>{" "}
        <span className="text-ink-2">{texto}</span>
      </span>
      <span className="font-mono text-[12px] text-ink-3">
        {d.fecho
          ? t("guia.decisivas.fecho", { hora: lisboa(d.fecho) })
          : t("guia.decisivas.semFecho")}
      </span>
    </li>
  );
}

function porCorrida(decisivas: readonly Decisiva[]): Decisiva[][] {
  const grupos = new Map<string, Decisiva[]>();
  for (const d of decisivas) grupos.set(d.corrida.id, [...(grupos.get(d.corrida.id) ?? []), d]);
  return [...grupos.values()];
}

function PainelDecisivas({ decisivas }: { decisivas: readonly Decisiva[] }) {
  if (decisivas.length === 0) return null;
  const camaras = (["senado", "camara"] as const).filter((c) =>
    decisivas.some((d) => d.camara === c),
  );
  return (
    <Painel
      sobrelinha={t("guia.decisivas.sobrelinha")}
      titulo={t("guia.decisivas.titulo")}
      descricao={t("guia.decisivas.texto")}
      acessorio={<Estimativa />}
      fontes={[FONTE_FECHO]}
      metodo={t("guia.decisivas.metodo")}
    >
      <div className="grid gap-4 min-[720px]:grid-cols-2">
        {camaras.map((camara) => (
          <div key={camara} className="min-w-0">
            <h3 className="rotulo mb-1">{t(`guia.decisivas.camaras.${camara}`)}</h3>
            <ul className="flex flex-col text-sm">
              {porCorrida(decisivas.filter((d) => d.camara === camara)).map((ds) => (
                <LinhaDecisiva key={ds[0]?.corrida.id} ds={ds} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Painel>
  );
}

function MarcaDecisiva({ lados }: { lados: readonly Lado[] }) {
  if (lados.length === 0) return null;
  const chave =
    lados.length > 1
      ? "guia.hora.decisivaAmbos"
      : lados[0] === "D"
        ? "guia.hora.decisivaD"
        : "guia.hora.decisivaR";
  return (
    <span className="rounded-[2px] border border-signal bg-signal-wash px-1 py-0.5 font-mono text-[10.5px] leading-none tracking-[0.05em] whitespace-nowrap text-signal-ink uppercase">
      {t(chave)}
    </span>
  );
}

function LinhaCorrida({ c }: { c: CorridaGuia }) {
  return (
    <li className="flex flex-wrap items-center gap-x-2 gap-y-1 py-1">
      <Link href={caminhoPaginaCorrida(c.corrida.id)} className={`font-semibold ${LIGACAO}`}>
        {c.corrida.camara === "senado"
          ? t(c.corrida.especial ? "guia.hora.senadoEspecial" : "guia.hora.senado")
          : c.corrida.id}
      </Link>
      <span className="flex items-center gap-1.5 whitespace-nowrap">
        <Amostra cor={c.categoria} />
        {t(`previsao.categorias.${c.categoria}`)}
        <span className="font-mono text-[11.5px] text-ink-3">
          {t("guia.hora.probD", { p: formatarPercentagem(c.corrida.probD, 0) })}
        </span>
      </span>
      {c.consenso !== null ? (
        <span className="flex items-center gap-1.5 text-[12.5px] text-ink-2">
          <Amostra cor={corDe(c.consenso)} />
          {t("guia.hora.consenso", { categoria: rotuloPosicao(c.consenso) })}
        </span>
      ) : null}
      <MarcaDecisiva lados={c.decisivaPara} />
    </li>
  );
}

function BlocoEstado({ e }: { e: EstadoGuia }) {
  return (
    <li className="min-w-0">
      <p>
        <span className="font-semibold">{nomeEstado(e.estado)}</span>
        {e.todas ? (
          <span className="text-ink-3"> {t("fecho.todas", { hora: lisboa(e.todas) })}</span>
        ) : null}
      </p>
      {e.contagem ? (
        <p className="text-[12.5px] text-ink-2">{t(`guia.hora.contagem.${e.contagem}`)}</p>
      ) : null}
      <ul className="flex flex-col text-sm">
        {e.corridas.map((c) => (
          <LinhaCorrida key={c.corrida.id} c={c} />
        ))}
      </ul>
    </li>
  );
}

/** Página /resultados/guia/: o que seguir a cada hora de fecho das urnas. */
export function GuiaNoite({
  guia,
  prognosticos,
}: {
  guia: VistaGuia;
  prognosticos: VistaPrognosticos | null;
}) {
  const fontes = prognosticos ? [FONTE_FECHO, ...prognosticos.fontes] : [FONTE_FECHO];
  return (
    <div className="flex flex-col gap-4">
      <header className="min-w-0">
        <p className="rotulo mb-1">{t("guia.sobrelinha")}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {t("guia.titulo")}
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
          {t("guia.lede", { total: guia.total })}
        </p>
      </header>

      <PainelDecisivas decisivas={guia.decisivas} />

      <Painel
        sobrelinha={t("guia.hora.sobrelinha")}
        titulo={t("guia.hora.titulo")}
        descricao={t("guia.hora.texto")}
        fontes={fontes}
        metodo={t(prognosticos ? "guia.hora.metodo" : "guia.hora.metodoSemConsenso")}
      >
        <ol className="flex flex-col">
          {guia.blocos.map((b) => (
            <li
              key={b.instante}
              className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 border-t border-rule-2 py-3"
            >
              <span className="font-mono text-[15px] font-semibold">{lisboa(b.instante)}</span>
              <div className="flex min-w-0 flex-col gap-3">
                {b.estados.length > 0 ? (
                  <ul className="flex flex-col gap-3">
                    {b.estados.map((e) => (
                      <BlocoEstado key={e.estado} e={e} />
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-ink-2">{t("guia.hora.nenhuma")}</p>
                )}
                {b.semCorridas.length > 0 ? (
                  <p className="text-[12.5px] text-ink-3">
                    {t("guia.hora.semCorridas", {
                      estados: b.semCorridas.map((s) => nomeEstado(s)).join(", "),
                    })}
                  </p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      </Painel>
    </div>
  );
}
