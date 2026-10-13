import { Painel } from "@/components/ui/Painel.tsx";
import { Selo } from "@/components/ui/Selo.tsx";
import { t } from "@/lib/mensagens.ts";

/** Conteúdo provisório das secções que ainda não têm dados publicados. */
export function SeccaoEmPreparacao({ titulo, descricao }: { titulo: string; descricao: string }) {
  return (
    <Painel
      titulo={titulo}
      descricao={descricao}
      acessorio={<Selo variante="tracejado">{t("comum.emPreparacao")}</Selo>}
    >
      <p className="max-w-[62ch] text-ink-2">{t("seccoes.emPreparacaoTexto")}</p>
    </Painel>
  );
}
