import type { ComponentProps, ComponentType } from "react";

import { Container } from "@/components/ui/container";
import { CompassIcon, HeartUsersIcon, LockIcon, UserIcon, UsersIcon } from "@/components/ui/icons";

type Value = { title: string; body: string; Icon: ComponentType<ComponentProps<"svg">> };

/** Guiding principles. Keep them as intentions; don't name certifications or processes that don't exist. */
const values: Value[] = [
  {
    title: "Meaningful Connections",
    body: "We believe compatibility begins with understanding what matters to each person.",
    Icon: HeartUsersIcon,
  },
  {
    title: "Respect for Every Individual",
    body: "Every person's preferences, background, and aspirations deserve consideration.",
    Icon: UserIcon,
  },
  {
    title: "Family Participation",
    body: "We recognise the important role families can play in the matrimonial journey.",
    Icon: UsersIcon,
  },
  {
    title: "Transparency",
    body: "Clear information and honest expectations help people make informed decisions.",
    Icon: CompassIcon,
  },
  {
    title: "Privacy and Care",
    body: "Personal information should be handled responsibly, with appropriate privacy practices.",
    Icon: LockIcon,
  },
];

/** Five cards: three then two (centred) on desktop, two per row on tablets, one on phones. */
export function CoreValues() {
  return (
    <section aria-labelledby="values-title" className="bg-white py-14 sm:py-20">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="values-title" className="text-3xl font-semibold sm:text-4xl">
            What Matters to Us
          </h2>
          <p className="mt-3 text-lg text-pretty text-ink-muted">
            Principles that guide the experience we aim to create.
          </p>
        </div>

        <ul className="mt-10 flex flex-wrap justify-center gap-4 sm:mt-12 sm:gap-5">
          {values.map(({ title, body, Icon }) => (
            <li
              key={title}
              className="flex basis-full gap-4 rounded-xl border border-line bg-white p-5 transition-colors duration-200 hover:border-field-line/70 sm:basis-[calc(50%-0.625rem)] sm:flex-col sm:p-7 lg:basis-[calc(100%/3-0.84rem)]"
            >
              <span className="flex size-12 shrink-0 items-center justify-center rounded-full border border-accent-400 bg-accent-100 text-wine-600">
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
