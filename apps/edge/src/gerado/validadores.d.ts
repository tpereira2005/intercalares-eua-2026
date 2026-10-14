// Tipos de src/gerado/validadores.js (gerado por scripts/gerar-validadores.mjs).

export interface ErroValidacao {
  instancePath: string;
  message?: string;
}

export interface Validador {
  (dados: unknown): boolean;
  errors?: ErroValidacao[] | null;
}

export declare const ResultadosParciais: Validador;
export declare const ProjecaoNoite: Validador;
export declare const HistoricoNoite: Validador;
export declare const ChamadasRedacoes: Validador;
