import type { ComponentProps, ComponentType } from "react";

import { Container } from "@/components/ui/container";
import { CompassIcon, HeartIcon, SearchIcon, ShieldCheckIcon, UserIcon, UsersIcon } from "@/components/ui/icons";

type Benefit = { title: string; body: string; Icon: ComponentType<ComponentProps<"svg">> };

/**
 * Reasons to choose the service. Each line is limited to what the site does
 * today or what docs/ plans, worded so nothing reads as already live or guaranteed.
 */
const benefits: Benefit[] = [
  {
    title: "Thoughtful Match Discovery",
    body: "Explore profiles using the preferences that matter to you.",
    Icon: HeartIcon,
  },
  {
    title: "Detailed Member Profiles",
    body: "Profiles are designed to cover personal, educational, professional and family details in one place.",
    Icon: UserIcon,
  },
  {
    title: "Search That Fits Your Preferences",
    body: "Narrow down by age, height, religion, community, location, marital status and mother tongue.",
    Icon: SearchIcon,
  },
  {
    title: "Family-Inclusive Journey",
    body: "A profile can be created by you or by a parent, sibling or relative, so families can take part from the start.",
    Icon: UsersIcon,
  },
  {
    title: "Privacy-Conscious Experience",
    body: "Our public pages never show contact details or private photos, and members choose who sees theirs.",
    Icon: ShieldCheckIcon,
  },
  {
    title: "A Clear Path Forward",
    body: "Simple steps from profile to first conversation, with answers to common questions in our FAQ.",
    Icon: CompassIcon,
  },
];

export function WhyChooseUs() {
  return (
    <section id="why-us" aria-labelledby="why-us-title" className="scroll-mt-20 bg-mist py-14 sm:py-20">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="why-us-title" className="text-3xl font-semibold sm:text-4xl">
            Why Families Choose Massil Matrimony
          </h2>
          <p className="mt-3 text-lg text-pretty text-ink-muted">
            Because finding a life partner deserves care, clarity, and thoughtful decisions.
          </p>
        </div>

        <ul className="mt-10 grid gap-4 sm:mt-12 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3 lg:gap-6">
          {benefits.map(({ title, body, Icon }) => (
            <li
              key={title}
              className="flex gap-4 rounded-xl border border-line bg-white p-5 transition-colors duration-200 hover:border-field-line/70 sm:flex-col sm:p-7"
            >
              <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-wine-600">
                <Icon className="size-6" />
              </span>
              <div className="min-w-0">
                <h3 className="font-sans text-lg leading-snug font-medium text-ink sm:mt-1">{title}</h3>
                <p className="mt-1.5 text-base leading-relaxed text-pretty text-ink-muted">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
