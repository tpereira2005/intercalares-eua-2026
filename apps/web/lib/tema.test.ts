import { describe, expect, it } from "vitest";
import { atributoTema, CHAVE_TEMA, eTema, lerTema, SCRIPT_TEMA } from "./tema.ts";

function armazenamento(valor: string | null) {
  return { getItem: (chave: string) => (chave === CHAVE_TEMA ? valor : null) };
}

describe("tema", () => {
  it("segue o sistema por omissão", () => {
    expect(lerTema(armazenamento(null))).toBe("sistema");
    expect(lerTema(undefined)).toBe("sistema");
  });

  it("lê a escolha guardada", () => {
    expect(lerTema(armazenamento("escuro"))).toBe("escuro");
  });

  it("ignora valores inválidos e erros de acesso", () => {
    expect(lerTema(armazenamento("roxo"))).toBe("sistema");
    const comErro = {
      getItem: () => {
        throw new Error("bloqueado");
      },
    };
    expect(lerTema(comErro)).toBe("sistema");
  });

  it("traduz o tema para o atributo data-theme", () => {
    expect(atributoTema("claro")).toBe("light");
    expect(atributoTema("escuro")).toBe("dark");
    expect(atributoTema("sistema")).toBeNull();
    expect(eTema("claro")).toBe(true);
    expect(eTema(1)).toBe(false);
  });

  it("aplica o tema guardado antes da primeira pintura", () => {
    const atributos = new Map<string, string>();
    const documento = {
      documentElement: {
        setAttribute: (nome: string, valor: string) => atributos.set(nome, valor),
      },
    };
    // O script é texto embutido no HTML; executá-lo assim é a forma fiel de o testar.
    // eslint-disable-next-line @typescript-eslint/no-implied-eval
    const executar = new Function("localStorage", "document", SCRIPT_TEMA) as (
      a: unknown,
      d: unknown,
    ) => void;
    executar(armazenamento("escuro"), documento);
    expect(atributos.get("data-theme")).toBe("dark");
  });
});
