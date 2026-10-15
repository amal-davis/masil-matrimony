import Image from "next/image";
import Link from "next/link";

import { config } from "@/lib/config";
import { cn } from "@/lib/utils";

import monogram from "@/public/images/masil-matrimony-monogram.png";

/**
 * Gold MM monogram (trimmed from the brand logo) with a text wordmark, for wine surfaces.
 * The full logo's baked-in wordmark is unreadable at header size, so the name is set as text.
 */
export function SiteLogo({ className, onClick }: { className?: string; onClick?: () => void }) {
  const [first, ...rest] = config.siteName.split(" ");

  return (
    <Link
      href="/"
      onClick={onClick}
      aria-label={`${config.siteName} home`}
      className={cn(
        "flex shrink-0 items-center gap-2.5 rounded-sm focus-visible:outline-gold sm:gap-3",
        className,
      )}
    >
      <Image
        src={monogram}
        alt=""
        loading="eager"
        className="h-9 w-auto shrink-0 drop-shadow-[0_4px_8px_rgba(0,0,0,0.35)] sm:h-10"
        sizes="48px"
      />
      <span className="flex flex-col leading-none">
        <span className="font-display text-[1.375rem] font-medium text-ivory sm:text-2xl">{first}</span>
        {rest.length > 0 && (
          <span className="mt-1 text-[0.625rem] font-normal tracking-[0.42em] text-gold uppercase sm:text-[0.6875rem]">
            {rest.join(" ")}
          </span>
        )}
      </span>
    </Link>
  );
}
