import Link from "next/link";

export default function NaoEncontrado() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center gap-4 px-4">
      <h1 className="text-3xl font-bold">Página não encontrada</h1>
      <Link href="/" className="underline">
        Voltar ao início
      </Link>
    </main>
  );
}
