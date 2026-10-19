import type { ComponentProps, ComponentType } from "react";

import { Container } from "@/components/ui/container";
import { MessagesIcon, SearchIcon, SlidersIcon, UserPlusIcon } from "@/components/ui/icons";

type Step = { title: string; body: string; Icon: ComponentType<ComponentProps<"svg">> };

/** The member journey. Steps describe the planned flow; see the note below the list. */
const steps: Step[] = [
  {
    title: "Create Your Profile",
    body: "Start by sharing essential personal, educational, professional, and family details.",
    Icon: UserPlusIcon,
  },
  {
    title: "Set Your Preferences",
    body: "Tell us about the qualities, values, and preferences that matter to you in a life partner.",
    Icon: SlidersIcon,
  },
  {
    title: "Discover Potential Matches",
    body: "Explore member profiles and use the search filters to find people who align with your preferences.",
    Icon: SearchIcon,
  },
  {
    title: "Take the Next Step",
    body: "Send an interest to profiles you like. Contact details are shared only as each member's privacy settings allow.",
    Icon: MessagesIcon,
  },
];

const pad = (value: number) => String(value).padStart(2, "0");

/**
 * Four connected steps: a vertical timeline on phones, a 2×2 grid on tablets
 * and a horizontal timeline from lg.
 */
export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-it-works-title" className="scroll-mt-20 bg-white py-14 sm:py-20">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="how-it-works-title" className="text-3xl font-semibold sm:text-4xl">
            How It Works
          </h2>
          <p className="mt-3 text-lg text-pretty text-ink-muted">
            A thoughtful journey towards finding someone who shares your values and vision for life.
          </p>
        </div>

        <ol className="mt-10 grid gap-0 sm:mt-14 md:grid-cols-2 md:gap-x-8 md:gap-y-10 lg:grid-cols-4 lg:gap-x-6">
          {steps.map(({ title, body, Icon }, index) => {
            const last = index === steps.length - 1;
            return (
              <li key={title} className="relative flex gap-5 pb-8 last:pb-0 md:pb-0 lg:flex-col lg:items-center lg:text-center">
                {!last && (
                  <>
                    {/* Phones: a line down to the next step. */}
                    <span aria-hidden="true" className="absolute top-16 bottom-2 left-7 w-px bg-accent-400/60 md:hidden" />
                    {/* Desktop: a line across to the next step. */}
                    <span
                      aria-hidden="true"
                      className="absolute top-7 left-[calc(50%+2.75rem)] hidden h-px w-[calc(100%-5.5rem+1.5rem)] bg-accent-400/60 lg:block"
                    />
                  </>
                )}

                <span className="relative flex size-14 shrink-0 items-center justify-center rounded-full border border-accent-400 bg-accent-100 text-wine-600">
                  <Icon className="size-6" />
                </span>

                <div className="min-w-0 pt-1 lg:pt-0">
                  <p className="text-sm font-medium text-wine-600 tabular-nums lg:mt-5">
                    <span className="sr-only">Step </span>
                    {pad(index + 1)}
                  </p>
                  <h3 className="mt-1 font-sans text-lg leading-snug font-medium text-ink sm:text-xl">{title}</h3>
                  <p className="mt-2 text-base leading-relaxed text-pretty text-ink-muted lg:mx-auto lg:max-w-64">
                    {body}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>

        <p className="mx-auto mt-10 max-w-2xl text-center text-base text-ink-muted sm:mt-12">
          Member accounts, profiles and interests open with member registration. You can already try the partner
          search filters above.
        </p>
      </Container>
    </section>
  );
}
