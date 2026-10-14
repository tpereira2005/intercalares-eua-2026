import { describe, expect, it } from "vitest";
import { DOCUMENTOS, ancora, converter, lerDocumento, reescreverLigacao } from "./metodologia.ts";

describe("documentos de metodologia", () => {
  it("dá âncoras iguais às do GitHub", () => {
    expect(ancora("4. Sondagens do Senado")).toBe("4-sondagens-do-senado");
    expect(ancora("3.1 Composição")).toBe("31-composição");
  });

  it("leva as ligações entre documentos para o site e as outras para o GitHub", () => {
    expect(reescreverLigacao("voto-antecipado.md")).toBe("/metodologia/voto-antecipado/");
    expect(reescreverLigacao("previsao.md#2-fundamentos")).toBe(
      "/metodologia/previsao/#2-fundamentos",
    );
    expect(reescreverLigacao("../noite-eleitoral-operacao.md")).toMatch(
      /blob\/main\/docs\/noite-eleitoral-operacao\.md$/,
    );
    expect(reescreverLigacao("https://dl.ncsbe.gov")).toBe("https://dl.ncsbe.gov");
  });

  it("separa o título, guarda as secções e envolve as tabelas", () => {
    const d = converter(
      "previsao",
      "# Título\n\nResumo com [ligação](resultados.md).\n\n## 1. Dados\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
      "Tabela",
    );
    expect(d.titulo).toBe("Título");
    expect(d.resumo).toBe("Resumo com ligação.");
    expect(d.seccoes).toEqual([{ id: "1-dados", titulo: "1. Dados" }]);
    expect(d.html).toContain('<h2 id="1-dados">');
    expect(d.html).toContain('href="/metodologia/resultados/"');
    expect(d.html).toContain('<div class="tabela-deslizante"');
    expect(d.html).not.toContain("<h1");
  });

  it("dá um nome único a cada tabela e a cada bloco de código com deslocamento", () => {
    const tabela = "| a |\n|---|\n| 1 |\n";
    const d = converter(
      "previsao",
      `# T\n\n${tabela}\n${tabela}\n\`\`\`\ncódigo\n\`\`\`\n\n\`\`\`\noutro\n\`\`\`\n`,
      "Tabela {n}",
      "Código {n}",
    );
    expect(d.html).toContain('aria-label="Tabela 1"');
    expect(d.html).toContain('aria-label="Tabela 2"');
    expect(d.html).toContain('<pre tabindex="0" role="region" aria-label="Código 1">');
    expect(d.html).toContain('aria-label="Código 2"');
  });

  it("tira o prefixo Metodologia do título", () => {
    expect(converter("previsao", "# Metodologia: previsão da Câmara\n\nTexto.", "T").titulo).toBe(
      "Previsão da Câmara",
    );
  });

  it("lê todos os documentos do repositório", () => {
    for (const documento of DOCUMENTOS) {
      expect(lerDocumento(documento, "Tabela")?.seccoes.length).toBeGreaterThan(0);
    }
  });
});
