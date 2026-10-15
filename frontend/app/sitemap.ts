import type { MetadataRoute } from "next";

import { config } from "@/lib/config";

export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: `${config.siteUrl}/`, changeFrequency: "weekly", priority: 1 }];
}
