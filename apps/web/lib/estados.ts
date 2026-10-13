/**
 * Estados dos EUA: nome em português de Portugal e posição no mapa em grelha
 * (12 colunas × 8 linhas, um quadrado por estado, como no protótipo aprovado).
 */

import type { CodigoEstado } from "@intercalares/contratos";

export interface Estado {
  codigo: CodigoEstado;
  nome: string;
  coluna: number;
  linha: number;
}

export const COLUNAS_GRELHA = 12;
export const LINHAS_GRELHA = 8;

export const ESTADOS: readonly Estado[] = [
  { codigo: "AK", nome: "Alasca", coluna: 0, linha: 0 },
  { codigo: "ME", nome: "Maine", coluna: 11, linha: 0 },
  { codigo: "VT", nome: "Vermont", coluna: 10, linha: 1 },
  { codigo: "NH", nome: "Nova Hampshire", coluna: 11, linha: 1 },
  { codigo: "WA", nome: "Washington", coluna: 1, linha: 2 },
  { codigo: "ID", nome: "Idaho", coluna: 2, linha: 2 },
  { codigo: "MT", nome: "Montana", coluna: 3, linha: 2 },
  { codigo: "ND", nome: "Dacota do Norte", coluna: 4, linha: 2 },
  { codigo: "MN", nome: "Minnesota", coluna: 5, linha: 2 },
  { codigo: "IL", nome: "Illinois", coluna: 6, linha: 2 },
  { codigo: "WI", nome: "Wisconsin", coluna: 7, linha: 2 },
  { codigo: "MI", nome: "Michigan", coluna: 8, linha: 2 },
  { codigo: "NY", nome: "Nova Iorque", coluna: 9, linha: 2 },
  { codigo: "RI", nome: "Rhode Island", coluna: 10, linha: 2 },
  { codigo: "MA", nome: "Massachusetts", coluna: 11, linha: 2 },
  { codigo: "OR", nome: "Oregon", coluna: 1, linha: 3 },
  { codigo: "NV", nome: "Nevada", coluna: 2, linha: 3 },
  { codigo: "WY", nome: "Wyoming", coluna: 3, linha: 3 },
  { codigo: "SD", nome: "Dacota do Sul", coluna: 4, linha: 3 },
  { codigo: "IA", nome: "Iowa", coluna: 5, linha: 3 },
  { codigo: "IN", nome: "Indiana", coluna: 6, linha: 3 },
  { codigo: "OH", nome: "Ohio", coluna: 7, linha: 3 },
  { codigo: "PA", nome: "Pensilvânia", coluna: 8, linha: 3 },
  { codigo: "NJ", nome: "Nova Jérsia", coluna: 9, linha: 3 },
  { codigo: "CT", nome: "Connecticut", coluna: 10, linha: 3 },
  { codigo: "CA", nome: "Califórnia", coluna: 1, linha: 4 },
  { codigo: "UT", nome: "Utah", coluna: 2, linha: 4 },
  { codigo: "CO", nome: "Colorado", coluna: 3, linha: 4 },
  { codigo: "NE", nome: "Nebraska", coluna: 4, linha: 4 },
  { codigo: "MO", nome: "Missouri", coluna: 5, linha: 4 },
  { codigo: "KY", nome: "Kentucky", coluna: 6, linha: 4 },
  { codigo: "WV", nome: "Virgínia Ocidental", coluna: 7, linha: 4 },
  { codigo: "VA", nome: "Virgínia", coluna: 8, linha: 4 },
  { codigo: "MD", nome: "Maryland", coluna: 9, linha: 4 },
  { codigo: "DE", nome: "Delaware", coluna: 10, linha: 4 },
  { codigo: "AZ", nome: "Arizona", coluna: 2, linha: 5 },
  { codigo: "NM", nome: "Novo México", coluna: 3, linha: 5 },
  { codigo: "KS", nome: "Kansas", coluna: 4, linha: 5 },
  { codigo: "AR", nome: "Arkansas", coluna: 5, linha: 5 },
  { codigo: "TN", nome: "Tennessee", coluna: 6, linha: 5 },
  { codigo: "NC", nome: "Carolina do Norte", coluna: 7, linha: 5 },
  { codigo: "SC", nome: "Carolina do Sul", coluna: 8, linha: 5 },
  { codigo: "DC", nome: "Distrito de Colúmbia", coluna: 9, linha: 5 },
  { codigo: "OK", nome: "Oklahoma", coluna: 4, linha: 6 },
  { codigo: "LA", nome: "Luisiana", coluna: 5, linha: 6 },
  { codigo: "MS", nome: "Mississípi", coluna: 6, linha: 6 },
  { codigo: "AL", nome: "Alabama", coluna: 7, linha: 6 },
  { codigo: "GA", nome: "Geórgia", coluna: 8, linha: 6 },
  { codigo: "HI", nome: "Havai", coluna: 0, linha: 7 },
  { codigo: "TX", nome: "Texas", coluna: 4, linha: 7 },
  { codigo: "FL", nome: "Flórida", coluna: 9, linha: 7 },
];

const POR_CODIGO = new Map(ESTADOS.map((e) => [e.codigo, e]));

export function nomeEstado(codigo: CodigoEstado): string {
  return POR_CODIGO.get(codigo)?.nome ?? codigo;
}
