import { Painel } from "@/components/ui/Painel.tsx";
import { formatarData, formatarPercentagem } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";
import type { AlteracaoVista, VistaAlteracoes } from "@/lib/previsao/explorador.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

function AntesDepois({ valor }: { valor: AlteracaoVista["camara"] }) {
  const depois = formatarPercentagem(valor.depois, 0);
  if (valor.antes === null) return <>{t("previsao.alteracoes.primeira", { depois })}</>;
  const antes = formatarPercentagem(valor.antes, 0);
  return (
    <>
      {antes === depois
        ? t("previsao.alteracoes.semMudanca", { depois })
        : `D ${antes} → ${depois}`}
    </>
  );
}

function numeroPr(url: string): string {
  return /\/pull\/(\d+)/.exec(url)?.[1] ?? url;
}

/** Registo público das alterações do método, com o efeito em cada câmara. */
export function PainelAlteracoes({ alteracoes }: { alteracoes: VistaAlteracoes }) {
  if (alteracoes.lista.length === 0) return null;
  return (
    <Painel
      sobrelinha={t("previsao.alteracoes.sobrelinha")}
      titulo={t("previsao.alteracoes.titulo")}
      descricao={t("previsao.alteracoes.texto")}
      fontes={alteracoes.fontes}
      metodo={t("previsao.alteracoes.metodo")}
    >
      <ol className="flex flex-col">
        {alteracoes.lista.map((a) => (
          <li
            key={`${a.data}-${a.pr}`}
            className="grid gap-x-4 gap-y-1 border-t border-rule-2 py-2.5 first:border-t-0 first:pt-0 sm:grid-cols-[8.5rem_minmax(0,1fr)]"
          >
            <p className="font-mono text-[12px] text-ink-3">
              {formatarData(new Date(`${a.data}T12:00:00Z`))}
            </p>
            <div className="flex min-w-0 flex-col gap-1">
              <p className="text-sm">{a.descricao}</p>
              <p className="flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[12px] text-ink-2">
                <span>
                  {t("previsao.alteracoes.camara")} <AntesDepois valor={a.camara} />
                </span>
                <span>
                  {t("previsao.alteracoes.senado")} <AntesDepois valor={a.senado} />
                </span>
                <a href={a.pr} rel="noopener noreferrer" className={LIGACAO}>
                  {t("previsao.alteracoes.pr", { numero: numeroPr(a.pr) })}
                </a>
              </p>
            </div>
          </li>
        ))}
      </ol>
    </Painel>
  );
}
