import { diasAteEleicao, formatarData, DIA_DA_ELEICAO } from "@/lib/formatacao.ts";
import { t } from "@/lib/mensagens.ts";

export default function Inicio() {
  // Calculado no momento do build; o site é reconstruído a cada atualização de dados.
  const dias = diasAteEleicao(new Date());

  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-4 px-4 py-16">
      <h1 className="text-4xl font-bold tracking-tight">{t("inicio.titulo")}</h1>
      <p className="text-lg text-texto-suave">{t("inicio.subtitulo")}</p>
      <p>
        <time dateTime="2026-11-03">{formatarData(DIA_DA_ELEICAO)}</time>
        {dias > 0 ? ` · ${t("inicio.contagemDecrescente", { dias })}` : null}
      </p>
      <p className="text-texto-suave">{t("inicio.emConstrucao")}</p>
    </main>
  );
}
