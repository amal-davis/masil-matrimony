import type { MetadataRoute } from "next";

import { legalConfig } from "@/features/legal/config";
import { config } from "@/lib/config";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${config.siteUrl}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${config.siteUrl}/about-us`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${config.siteUrl}/success-stories`, changeFrequency: "weekly", priority: 0.6 },
    { url: `${config.siteUrl}/our-packages`, changeFrequency: "monthly", priority: 0.7 },
    { url: `${config.siteUrl}/contact`, changeFrequency: "monthly", priority: 0.5 },
    { url: `${config.siteUrl}/faq`, changeFrequency: "monthly", priority: 0.5 },
    // Listed only once the drafts are approved; until then they are noindex.
    ...(legalConfig.approvedForPublication
      ? [
          { url: `${config.siteUrl}/privacy-policy`, changeFrequency: "yearly" as const, priority: 0.3 },
          { url: `${config.siteUrl}/terms-and-conditions`, changeFrequency: "yearly" as const, priority: 0.3 },
          { url: `${config.siteUrl}/refund-policy`, changeFrequency: "yearly" as const, priority: 0.3 },
          { url: `${config.siteUrl}/shipping-policy`, changeFrequency: "yearly" as const, priority: 0.3 },
        ]
      : []),
  ];
}
