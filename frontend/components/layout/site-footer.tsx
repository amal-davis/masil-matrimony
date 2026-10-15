import Link from "next/link";

import { Container } from "@/components/ui/container";
import { config } from "@/lib/config";
import { mainNav } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line bg-surface-muted">
      <Container className="flex flex-col gap-8 py-10 md:flex-row md:items-start md:justify-between">
        <div className="max-w-sm">
          <p className="font-display text-lg font-semibold text-brand-800">{config.siteName}</p>
          <p className="mt-2 text-sm text-ink-muted">
            A trusted, privacy-first matrimonial service for families looking for the right match.
          </p>
        </div>

        <nav aria-label="Footer">
          <ul className="flex flex-col gap-2 text-sm text-ink-muted">
            {mainNav.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="hover:text-brand-700">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </Container>
      <div className="border-t border-line">
        <Container className="py-4 text-xs text-ink-muted">
          &copy; {config.siteName}. All rights reserved.
        </Container>
      </div>
    </footer>
  );
}
