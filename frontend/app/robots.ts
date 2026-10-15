import type { MetadataRoute } from "next";

import { config } from "@/lib/config";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Private areas planned for the member portal, admin panel and CRM.
      disallow: ["/status", "/dashboard", "/admin", "/crm"],
    },
    sitemap: `${config.siteUrl}/sitemap.xml`,
  };
}
