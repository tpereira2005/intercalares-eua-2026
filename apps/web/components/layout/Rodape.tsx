import Link from "next/link";
import { t } from "@/lib/mensagens.ts";

export function Rodape() {
  return (
    <footer className="contentor flex flex-wrap gap-x-4 gap-y-1 pb-8 font-mono text-[11.5px] leading-normal text-ink-3">
      <span>{t("rodape.texto")}</span>
      <a
        href="https://github.com/tpereira2005/intercalares-eua-2026"
        className="underline decoration-rule underline-offset-[3px]"
        rel="noopener noreferrer"
      >
        {t("rodape.codigo")}
      </a>
      <Link href="/sistema/" className="underline decoration-rule underline-offset-[3px]">
        {t("rodape.sistema")}
      </Link>
    </footer>
  );
}
