import type { Metadata } from "next";
import { CodigoDia } from "@/components/ui/CodigoDia.tsx";
import { FaixaKpis, Kpi } from "@/components/ui/Kpi.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { QualidadeDados } from "@/components/ui/QualidadeDados.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { formatarNumero, formatarPontos } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";

export const metadata: Metadata = {
  title: t("sistema.titulo"),
  robots: { index: false },
};

const CORES = [
  "paper",
  "sheet",
  "ink",
  "ink-2",
  "ink-3",
  "rule",
  "signal",
  "signal-wash",
  "dem",
  "rep",
  "una",
  "up",
  "down",
] as const;

const PADROES: Partial<Record<(typeof CORES)[number], string>> = {
  dem: "fundo-dem",
  rep: "fundo-rep",
  una: "fundo-una",
};

export default function SistemaVisual() {
  return (
    <>
      <header className="flex flex-col gap-1 pt-2">
        <h1 className="font-display text-4xl leading-none font-bold">{t("sistema.titulo")}</h1>
        <p className="max-w-[62ch] text-sm text-ink-2">{t("sistema.descricao")}</p>
      </header>

      <Painel titulo={t("sistema.cores")}>
        <ul className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2.5">
          {CORES.map((cor) => (
            <li key={cor} className="overflow-hidden rounded-md border border-rule bg-sheet">
              <i
                className={`block h-[54px] ${PADROES[cor] ?? ""}`}
                style={PADROES[cor] ? undefined : { background: `var(--${cor})` }}
              />
              <div className="px-2.5 py-2 text-[12.5px] leading-snug">
                <b className="block font-semibold">{t(`sistema.papeis.${cor}`)}</b>
                <code className="font-mono text-[11px] text-ink-3">--{cor}</code>
              </div>
            </li>
          ))}
        </ul>
      </Painel>

      <Painel titulo={t("sistema.tipografia")}>
        <div className="flex flex-col gap-3.5">
          <p className="font-display text-[38px] leading-none font-extrabold">
            {t("sistema.letras.display")}
          </p>
          <p className="text-[15px]">{t("sistema.letras.body")}</p>
          <p className="rotulo">{t("sistema.letras.data")}</p>
        </div>
      </Painel>

      <Painel titulo={t("sistema.componentes")}>
        <div className="flex flex-wrap items-center gap-2.5">
          <Selo variante="tracejado">{t("comum.selos.ilustrativo")}</Selo>
          <Selo variante="tracejado">{t("comum.selos.estimativa")}</Selo>
          <Selo variante="solido">{t("comum.selos.oficial")}</Selo>
          <Selo variante="sinal">
            <span className="ao-vivo inline-flex items-center gap-1.5">
              {t("comum.selos.aoVivo")}
            </span>
          </Selo>
          <CodigoDia dias={21} />
          <QualidadeDados nivel="individual" comTexto />
          <QualidadeDados nivel="parcial" comTexto />
          <QualidadeDados nivel="agregado" comTexto />
        </div>
        <FaixaKpis>
          <Kpi
            rotulo={t("sistema.exemplos.kpi1")}
            valor={formatarNumero(1234567)}
            detalhe={t("sistema.exemplos.detalhe")}
          />
          <Kpi
            rotulo={t("sistema.exemplos.kpi2")}
            valor={formatarPontos(0.021)}
            detalhe={t("sistema.exemplos.detalhe")}
          />
          <Kpi rotulo={t("sistema.exemplos.kpi3")} valor={<CodigoDia dias={21} />} />
        </FaixaKpis>
        <Painel
          sobrelinha={t("sistema.exemplos.painelSobrelinha")}
          titulo={t("sistema.exemplos.painelTitulo")}
          descricao={t("sistema.exemplos.painelDescricao")}
          acessorio={<Selo>{t("comum.selos.ilustrativo")}</Selo>}
          fontes={[{ nome: t("sistema.exemplos.fonte") }]}
          metodo={t("sistema.exemplos.metodo")}
        >
          <div className="flex h-3 overflow-hidden rounded-[2px] bg-rule-2">
            <span className="fundo-dem w-[46%]" />
            <span className="fundo-una w-[8%]" />
            <span className="fundo-rep w-[46%]" />
          </div>
        </Painel>
      </Painel>
    </>
  );
}
