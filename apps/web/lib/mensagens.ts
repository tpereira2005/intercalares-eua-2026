import mensagens from "@/messages/pt-PT.json";

type Mensagens = typeof mensagens;
type Folhas<T, Prefixo extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${Prefixo}${K}` : Folhas<T[K], `${Prefixo}${K}.`>;
}[keyof T & string];

/** Chave de uma mensagem, por exemplo "inicio.titulo". Verificada em tempo de compilação. */
export type ChaveMensagem = Folhas<Mensagens>;

/**
 * Devolve o texto PT-PT de uma chave, substituindo marcadores `{nome}`.
 * Todo o texto visível do site passa por aqui.
 */
export function t(chave: ChaveMensagem, valores: Record<string, string | number> = {}): string {
  let atual: unknown = mensagens;
  for (const parte of chave.split(".")) {
    atual = (atual as Record<string, unknown>)[parte];
  }
  if (typeof atual !== "string") {
    throw new Error(`Mensagem em falta: ${chave}`);
  }
  return atual.replace(/\{(\w+)\}/g, (marcador, nome: string) => {
    const valor = valores[nome];
    return valor === undefined ? marcador : String(valor);
  });
}
