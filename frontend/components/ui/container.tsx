import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const widths = {
  default: "max-w-6xl",
  /** For dense grids that benefit from more room on large screens (e.g. profile cards). */
  wide: "max-w-[88rem]",
};

export function Container({
  className,
  size = "default",
  ...props
}: ComponentProps<"div"> & { size?: keyof typeof widths }) {
  return <div className={cn("mx-auto w-full px-4 sm:px-6 lg:px-8", widths[size], className)} {...props} />;
}
