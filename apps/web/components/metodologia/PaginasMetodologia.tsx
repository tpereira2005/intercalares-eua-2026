import Link from "next/link";
import { t } from "@/lib/mensagens.ts";
import { caminhoMetodologia, REPOSITORIO, type DocumentoMetodologia } from "@/lib/metodologia.ts";

const LIGACAO = "text-ink underline decoration-rule underline-offset-[3px]";

/** Índice: um cartão por documento, com o primeiro parágrafo e as secções. */
export function IndiceMetodologia({ documentos }: { documentos: readonly DocumentoMetodologia[] }) {
  return (
    <div className="flex flex-col gap-4">
      <header className="min-w-0">
        <p className="rotulo mb-1">{t("metodologia.sobrelinha")}</p>
        <h1 className="font-display text-[clamp(30px,5vw,40px)] leading-[1.02] font-bold">
          {t("seccoes.metodologia.titulo")}
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[15.5px] text-ink-2">{t("metodologia.lede")}</p>
      </header>
      <ul className="grid gap-4 md:grid-cols-2">
        {documentos.map((d) => (
          <li
            key={d.documento}
            className="flex min-w-0 flex-col gap-2 rounded-md border border-rule bg-sheet px-[18px] py-3.5"
          >
            <p className="rotulo">{t(`metodologia.grupos.${d.documento}`)}</p>
            <h2 className="text-[17px] leading-snug font-semibold">
              <Link href={caminhoMetodologia(d.documento)} className={LIGACAO}>
                {d.titulo}
              </Link>
            </h2>
            <p className="line-clamp-4 text-sm text-ink-2">{d.resumo}</p>
            <p className="font-mono text-[11px] text-ink-3">
              {t("metodologia.seccoes", { n: d.seccoes.length })}
            </p>
          </li>
        ))}
      </ul>
      <section className="rounded-md border border-rule bg-sheet px-[18px] py-3.5 text-sm">
        <h2 className="rotulo mb-2">{t("metodologia.codigo.titulo")}</h2>
        <p className="max-w-[72ch] text-ink-2">{t("metodologia.codigo.texto")}</p>
        <p className="mt-2">
          <a
            href={REPOSITORIO.replace(/\/blob\/main$/, "")}
            rel="noopener noreferrer"
            className={LIGACAO}
          >
            {t("metodologia.codigo.ligacao")}
          </a>
        </p>
      </section>
    </div>
  );
}

/** Um documento: título, índice das secções e o texto do repositório. */
export function PaginaDocumento({ documento: d }: { documento: DocumentoMetodologia }) {
  return (
    <article className="flex flex-col gap-5">
      <header className="min-w-0">
        <p className="rotulo mb-1">
          <Link href="/metodologia/" className={LIGACAO}>
            {t("seccoes.metodologia.titulo")}
          </Link>
          {" · "}
          {t(`metodologia.grupos.${d.documento}`)}
        </p>
        <h1 className="font-display text-[clamp(28px,5vw,38px)] leading-[1.05] font-bold">
          {d.titulo}
        </h1>
      </header>
      {d.seccoes.length > 1 ? (
        <nav
          aria-label={t("metodologia.indiceAria")}
          className="rounded-md border border-rule bg-sheet px-[18px] py-3 text-sm"
        >
          <p className="rotulo mb-1.5">{t("metodologia.indice")}</p>
          <ol className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            {d.seccoes.map((s) => (
              <li key={s.id} className="min-w-0">
                <a href={`#${s.id}`} className={LIGACAO}>
                  {s.titulo}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <div className="prosa min-w-0" dangerouslySetInnerHTML={{ __html: d.html }} />
      <p className="font-mono text-[11px] text-ink-3">
        {t("metodologia.fonte")}{" "}
        <a href={d.fonte} rel="noopener noreferrer" className={LIGACAO}>
          {`docs/metodologia/${d.documento}.md`}
        </a>
      </p>
    </article>
  );
}
