import type { MetadataRoute } from "next";

import { config } from "@/lib/config";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${config.siteUrl}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${config.siteUrl}/about-us`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${config.siteUrl}/success-stories`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${config.siteUrl}/contact`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${config.siteUrl}/faq`, changeFrequency: "monthly", priority: 0.5 },
  ];
}
