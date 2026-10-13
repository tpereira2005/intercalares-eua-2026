import type { Metadata } from "next";
import type { ReactNode } from "react";
import { t } from "@/lib/mensagens.ts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: t("site.nome"), template: `%s · ${t("site.nome")}` },
  description: t("site.descricao"),
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-PT">
      <body className="min-h-dvh font-sans antialiased">{children}</body>
    </html>
  );
}
