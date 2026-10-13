import { app } from "./app.ts";
import type { Env } from "./env.ts";

export default {
  fetch: app.fetch,

  /** Watchdog. Por agora só regista a execução; a orquestração chega na Fase 1. */
  scheduled(controller, env) {
    console.log(JSON.stringify({ evento: "cron", cron: controller.cron, ambiente: env.AMBIENTE }));
  },
} satisfies ExportedHandler<Env>;
