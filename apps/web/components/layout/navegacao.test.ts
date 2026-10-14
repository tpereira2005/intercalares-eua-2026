import { describe, expect, it } from "vitest";
import { seccaoAtiva } from "./Navegacao.tsx";

describe("navegação", () => {
  it("marca a secção do caminho atual", () => {
    expect(seccaoAtiva("/")).toBe("/");
    expect(seccaoAtiva("/voto-antecipado/")).toBe("/voto-antecipado/");
    expect(seccaoAtiva("/voto-antecipado/nc")).toBe("/voto-antecipado/");
    expect(seccaoAtiva("/corridas/nc-s/")).toBe("/previsao/");
    expect(seccaoAtiva("/sistema/")).toBeNull();
  });
});
