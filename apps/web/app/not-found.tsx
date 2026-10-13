import Link from "next/link";
import { Painel } from "@/components/ui/Painel.tsx";
import { t } from "@/lib/mensagens.ts";

export default function NaoEncontrado() {
  return (
    <Painel titulo={t("naoEncontrado.titulo")} nivelTitulo="h1">
      <Link href="/" className="underline decoration-rule underline-offset-[3px]">
        {t("naoEncontrado.voltar")}
      </Link>
    </Painel>
  );
}
