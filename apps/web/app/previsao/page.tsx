import type { Metadata } from "next";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { t } from "@/lib/mensagens.ts";

export const metadata: Metadata = { title: t("seccoes.previsao.titulo") };

/** Esqueleto da previsão: os painéis ganham dados quando o modelo publicar o seu contrato. */
const PAINEIS = ["camara", "senado", "corridas", "sondagens"] as const;

export default function Pagina() {
  return (
    <div className="flex flex-col gap-4">
      <header className="min-w-0">
        <p className="rotulo mb-1">{t("previsao.sobrelinha")}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {t("seccoes.previsao.titulo")}
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">{t("previsao.lede")}</p>
      </header>
      <div className="grid gap-4 min-[860px]:grid-cols-2">
        {PAINEIS.map((chave) => (
          <Painel
            key={chave}
            sobrelinha={t(`previsao.paineis.${chave}.sobrelinha`)}
            titulo={t(`previsao.paineis.${chave}.titulo`)}
            descricao={t(`previsao.paineis.${chave}.descricao`)}
            acessorio={<Selo variante="tracejado">{t("comum.emPreparacao")}</Selo>}
            metodo={t("previsao.metodo")}
          />
        ))}
      </div>
    </div>
  );
}
