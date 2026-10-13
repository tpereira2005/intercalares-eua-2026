import type { Metadata } from "next";
import { PaginaPrevisao } from "@/components/previsao/PaginaPrevisao.tsx";
import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { t } from "@/lib/mensagens.ts";
import { carregarPrevisao } from "@/lib/previsao/carregar.ts";

export const metadata: Metadata = {
  title: t("seccoes.previsao.titulo"),
  description: t("seccoes.previsao.descricao"),
};

export default function Pagina() {
  const dados = carregarPrevisao();
  if (dados) return <PaginaPrevisao dados={dados} />;
  return (
    <div className="flex flex-col gap-4">
      <header className="min-w-0">
        <p className="rotulo mb-1">{t("previsao.sobrelinha", { ano: 2026 })}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {t("seccoes.previsao.titulo")}
        </h1>
      </header>
      <Painel
        titulo={t("previsao.semPrevisao.titulo")}
        descricao={t("previsao.semPrevisao.texto")}
        acessorio={<Selo variante="tracejado">{t("comum.emPreparacao")}</Selo>}
        metodo={t("previsao.semPrevisao.metodo")}
      />
    </div>
  );
}
