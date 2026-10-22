import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { InfoIcon, MailIcon, PhoneIcon } from "@/components/ui/icons";
import { ArrowUpRightIcon, CameraIcon, CrownIcon, InboxIcon, UserCheckIcon } from "@/features/dashboard/components/icons";
import { Card, PageHeader, primaryButton, secondaryButton } from "@/features/dashboard/components/ui";
import { contactEmail, contactPhone } from "@/lib/site";

export const metadata: Metadata = { title: "Help & Support" };

const topics: { title: string; body: string; href: string; link: string; icon: ReactNode }[] = [
  {
    title: "Getting your profile approved",
    body: "Fill in the required details, submit your profile, and our team reviews it. You'll get a notification when it's approved or if changes are needed.",
    href: "/dashboard/my-profile",
    link: "Go to My Profile",
    icon: <UserCheckIcon className="size-5" />,
  },
  {
    title: "Photos and privacy",
    body: "Every photo is reviewed before members see it. You can limit your photos to members whose interest you've accepted.",
    href: "/dashboard/photos",
    link: "Manage photos",
    icon: <CameraIcon className="size-5" />,
  },
  {
    title: "Sending and answering interests",
    body: "Send an interest from a member's profile. When someone sends you one, accept to show mutual interest or decline politely.",
    href: "/dashboard/interests/received",
    link: "View interests",
    icon: <InboxIcon className="size-5" />,
  },
  {
    title: "Membership and payments",
    body: "Packages are activated by our team once payment is confirmed. Online payment isn't available yet.",
    href: "/dashboard/membership",
    link: "Membership & Upgrade",
    icon: <CrownIcon className="size-5" />,
  },
];

export default function HelpPage() {
  return (
    <>
      <PageHeader title="Help & Support" description="Answers to common questions, and how to reach our team." />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <ul className="grid gap-4 sm:grid-cols-2">
          {topics.map((topic) => (
            <li key={topic.title} className="flex flex-col rounded-xl border border-line bg-white p-5 sm:p-6">
              <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-lg bg-brand-50 text-wine-600">
                {topic.icon}
              </span>
              <h2 className="mt-4 text-base font-semibold">{topic.title}</h2>
              <p className="mt-1.5 flex-1 text-[0.9375rem] text-ink-muted">{topic.body}</p>
              <Link href={topic.href} className="mt-4 inline-flex min-h-11 items-center gap-1.5 self-start rounded-md text-[0.9375rem] font-medium text-wine-600 hover:text-wine-800 focus-visible:outline-wine-600">
                {topic.link}
                <ArrowUpRightIcon className="size-4" />
              </Link>
            </li>
          ))}
        </ul>

        <aside className="flex flex-col gap-6" aria-label="Contact our team">
          <Card title="Talk to our team" titleId="contact-title">
            <p className="text-[0.9375rem] text-ink-muted">Send us a message and we&apos;ll get back to you.</p>
            <div className="mt-4 flex flex-col gap-2">
              <Link href="/contact" className={primaryButton}>
                Send us a message
              </Link>
              {contactPhone && (
                <a href={`tel:${contactPhone.tel}`} className={secondaryButton}>
                  <PhoneIcon className="size-4.5" /> {contactPhone.display}
                </a>
              )}
              {contactEmail && (
                <a href={`mailto:${contactEmail}`} className={secondaryButton}>
                  <MailIcon className="size-4.5" /> {contactEmail}
                </a>
              )}
            </div>
          </Card>
          <Card title="Frequently asked questions" titleId="faq-title">
            <p className="text-[0.9375rem] text-ink-muted">Registration, verification, privacy and more.</p>
            <Link href="/faq" className={`${secondaryButton} mt-4 w-full`}>
              <InfoIcon className="size-4.5" /> Read the FAQs
            </Link>
          </Card>
        </aside>
      </div>
    </>
  );
}
