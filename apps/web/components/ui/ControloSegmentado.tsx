"use client";

export interface OpcaoSegmentada<V extends string> {
  valor: V;
  rotulo: string;
}

interface ControloSegmentadoProps<V extends string> {
  rotuloGrupo: string;
  opcoes: readonly OpcaoSegmentada<V>[];
  valor: V;
  aoMudar: (valor: V) => void;
}

/** Grupo de botões com oval de boletim, que se preenche na opção ativa. */
export function ControloSegmentado<V extends string>({
  rotuloGrupo,
  opcoes,
  valor,
  aoMudar,
}: ControloSegmentadoProps<V>) {
  return (
    <div
      role="group"
      aria-label={rotuloGrupo}
      className="inline-flex flex-wrap gap-0.5 rounded-sm bg-rule-2 p-0.5"
    >
      {opcoes.map((opcao) => {
        const ativa = opcao.valor === valor;
        return (
          <button
            key={opcao.valor}
            type="button"
            aria-pressed={ativa}
            onClick={() => {
              aoMudar(opcao.valor);
            }}
            className={`inline-flex cursor-pointer items-center gap-[7px] rounded-[2px] px-2.5 py-1.5 text-[13px] leading-[1.1] font-medium whitespace-nowrap ${
              ativa
                ? "bg-sheet text-ink shadow-[0_0_0_1px_var(--rule)]"
                : "text-ink-2 hover:text-ink"
            }`}
          >
            <span className="oval" aria-hidden="true" />
            {opcao.rotulo}
          </button>
        );
      })}
    </div>
  );
}
