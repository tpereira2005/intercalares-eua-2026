import type { Metadata } from "next";
import { MapaEstados } from "@/components/mapa/MapaEstados.tsx";
import { caminhoEstado } from "@/components/voto-antecipado/PaginaEstado.tsx";
import { t } from "@/lib/mensagens.ts";
import { carregarVistas } from "@/lib/voto-antecipado/carregar.ts";
import { resumirEstado } from "@/lib/voto-antecipado/resumo.ts";

export const metadata: Metadata = { title: t("seccoes.mapa.titulo") };

export default function Pagina() {
  // Os estados sem ficheiro aparecem a tracejado: o mapa fica pronto para vários estados.
  const resumos = carregarVistas().map(resumirEstado);
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
      <MapaEstados resumos={resumos} caminhos={caminhos} />
    </div>
  );
}
