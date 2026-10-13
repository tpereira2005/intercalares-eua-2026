import { describe, expect, it } from "vitest";
import { faseEm } from "./fases.ts";

describe("fases", () => {
  it("muda de fase no fecho das primeiras urnas e na manhã seguinte", () => {
    expect(faseEm(new Date("2026-10-13T12:00:00Z"))).toBe("antes");
    expect(faseEm(new Date("2026-11-03T22:59:59Z"))).toBe("antes");
    expect(faseEm(new Date("2026-11-03T23:00:00Z"))).toBe("noite");
    expect(faseEm(new Date("2026-11-04T12:00:00Z"))).toBe("depois");
  });
});
