/**
 * Tema visual: o do sistema por omissão, com escolha manual guardada no browser.
 * O atributo data-theme na raiz força "light" ou "dark" (ver styles/tokens.css).
 */

export const TEMAS = ["sistema", "claro", "escuro"] as const;
export type Tema = (typeof TEMAS)[number];

export const CHAVE_TEMA = "escrutinio-tema";
const EVENTO_TEMA = "escrutinio:tema";

export function eTema(valor: unknown): valor is Tema {
  return typeof valor === "string" && (TEMAS as readonly string[]).includes(valor);
}

/** Valor do atributo data-theme para um tema, ou null para seguir o sistema. */
export function atributoTema(tema: Tema): "light" | "dark" | null {
  if (tema === "claro") return "light";
  if (tema === "escuro") return "dark";
  return null;
}

/** Lê o tema guardado. Qualquer valor inválido ou erro de acesso cai em "sistema". */
export function lerTema(armazenamento: Pick<Storage, "getItem"> | undefined): Tema {
  try {
    const valor = armazenamento?.getItem(CHAVE_TEMA);
    return eTema(valor) ? valor : "sistema";
  } catch {
    return "sistema";
  }
}

export function aplicarTema(raiz: HTMLElement, tema: Tema): void {
  const atributo = atributoTema(tema);
  if (atributo === null) {
    raiz.removeAttribute("data-theme");
  } else {
    raiz.setAttribute("data-theme", atributo);
  }
}

/** Guarda e aplica o tema, e avisa os componentes que o mostram. */
export function escolherTema(tema: Tema): void {
  try {
    localStorage.setItem(CHAVE_TEMA, tema);
  } catch {
    // Sem armazenamento (navegação privada): o tema aplica-se só a esta página.
  }
  aplicarTema(document.documentElement, tema);
  window.dispatchEvent(new Event(EVENTO_TEMA));
}

export function subscreverTema(aoMudar: () => void): () => void {
  window.addEventListener(EVENTO_TEMA, aoMudar);
  window.addEventListener("storage", aoMudar);
  return () => {
    window.removeEventListener(EVENTO_TEMA, aoMudar);
    window.removeEventListener("storage", aoMudar);
  };
}

/**
 * Script embutido no <head> que aplica o tema guardado antes da primeira
 * pintura, para não haver um clarão do tema errado.
 */
export const SCRIPT_TEMA = `(function(){try{var t=localStorage.getItem(${JSON.stringify(CHAVE_TEMA)});var a=t==="claro"?"light":t==="escuro"?"dark":null;if(a)document.documentElement.setAttribute("data-theme",a)}catch(e){}})()`;
