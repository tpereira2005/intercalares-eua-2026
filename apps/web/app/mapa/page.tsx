import type { Metadata } from "next";
import { MapaEstados } from "@/components/mapa/MapaEstados.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { metadadosPagina } from "@/lib/metadados.ts";
import { t } from "@/lib/mensagens.ts";
import { carregarTodas, lerEstadosSemDados } from "@/lib/voto-antecipado/carregar.ts";
import { resumirTodos } from "@/lib/voto-antecipado/resumo.ts";

export const metadata: Metadata = metadadosPagina({
  titulo: t("seccoes.mapa.titulo"),
  descricao: t("seccoes.mapa.descricao"),
  caminho: "/mapa/",
  cartao: "mapa.png",
});

export default function Pagina() {
  // Os estados sem ficheiro aparecem a tracejado; os que o pipeline deixa de fora, com
  // motivo (fonte bloqueada ou sem fonte gratuita), aparecem riscados.
  const resumos = resumirTodos(carregarTodas());
  const comDados = new Set(resumos.map((r) => r.estado));
  const fora = lerEstadosSemDados()
    .filter((e) => !comDados.has(e.estado))
    .map(({ estado, motivo, nota }) => ({ estado, motivo, nota }));
  const anoBase = resumos.find((r) => r.anoBase !== null)?.anoBase ?? 2022;
  const caminhos = Object.fromEntries(resumos.map((r) => [r.estado, caminhoEstado(r.estado)]));
  return (
    <div className="flex flex-col gap-4">
      <header className="min-w-0">
        <p className="rotulo mb-1">{t("mapa.sobrelinha")}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {t("mapa.titulo")}
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">
          {t("mapa.lede", { ano: anoBase })}
        </p>
      </header>
      <MapaEstados resumos={resumos} caminhos={caminhos} fora={fora} />
    </div>
  );
}
