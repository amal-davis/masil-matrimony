import type { ComponentProps, ComponentType } from "react";

import { FacebookIcon, InstagramIcon, WhatsAppIcon, YouTubeIcon } from "@/components/ui/icons";
import type { SocialPlatform } from "@/lib/site";

/** Display name and icon for each social platform in `socialLinks` (lib/site.ts). */
export const socialMeta: Record<SocialPlatform, { label: string; Icon: ComponentType<ComponentProps<"svg">> }> = {
  instagram: { label: "Instagram", Icon: InstagramIcon },
  facebook: { label: "Facebook", Icon: FacebookIcon },
  youtube: { label: "YouTube", Icon: YouTubeIcon },
  whatsapp: { label: "WhatsApp", Icon: WhatsAppIcon },
};
