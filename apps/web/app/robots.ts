import type { MetadataRoute } from "next";
import { URL_SITE } from "@/lib/site.ts";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/sistema/"] },
    sitemap: new URL("/sitemap.xml", URL_SITE).toString(),
  };
}
