export type Faq = {
  /** Stable, URL-safe id; used for the accordion's element ids. */
  id: string;
  question: string;
  answer: string;
  /**
   * Not rendered. What the business must confirm before launch, because the
   * answer describes something not built or not yet decided.
   */
  reviewNote?: string;
};

/** How many questions the homepage shows; the FAQ page shows them all. */
export const HOMEPAGE_FAQ_COUNT = 6;

/**
 * Frequently asked questions, shared by the homepage section and /faq.
 *
 * Answers describe only what exists today or what docs/ plans, and say so
 * when a feature has not opened yet. Check every `reviewNote` before launch.
 */
export const faqs: Faq[] = [
  {
    id: "register",
    question: "How do I register on Massil Matrimony?",
    answer:
      "Use the free form at the top of our homepage: choose who the profile is for, then add a name, date of birth, mobile number, email address and a password. Your account is created straight away and you can then complete your profile from your dashboard. Our team reviews every profile before other members can see it.",
  },
  {
    id: "profile-details",
    question: "What information should I include in my matrimonial profile?",
    answer:
      "Cover the essentials, such as age, height, education, profession and location, along with your family background and, if it matters to you, religion and community. A few honest lines about yourself and the partner you hope to meet make a real difference. Share only what you are comfortable with.",
  },
  {
    id: "find-matches",
    question: "How can I find suitable matches on Massil Matrimony?",
    answer:
      "Use Search Your Partner on the homepage to filter by bride or groom, age, height, religion, community and location, with more filters for marital status and mother tongue. Profile results open together with member registration; until then, your chosen filters are kept in the page address so you can bookmark them.",
    reviewNote: "Update once profile search returns results (planned GET /profiles/search/).",
  },
  {
    id: "update-profile",
    question: "Can I update my profile after registration?",
    answer:
      "Yes. Once you have an account, you will be able to edit your details, photos and partner preferences whenever something changes. Keeping your profile current helps families see an accurate picture of you.",
    reviewNote: "Profile editing is planned (GET/PATCH /profiles/me/), not built yet.",
  },
  {
    id: "partner-preferences",
    question: "How can I manage my partner preferences?",
    answer:
      "Your partner preferences, such as age range, height, religion, community and location, will be saved with your profile and can be changed at any time. You can also run a one-off search with different filters without changing what you have saved.",
    reviewNote: "Saved preferences are planned with member profiles, not built yet.",
  },
  {
    id: "express-interest",
    question: "How do I express interest in a profile?",
    answer:
      "When you find a profile you like, you will be able to send an interest from that profile. The other member can accept or decline it, and contact details are shared only as that member's privacy settings allow.",
    reviewNote:
      "Interests are planned (POST /interests/). Confirm the rules for revealing contact details, which may also depend on membership.",
  },
  {
    id: "personal-information",
    question: "How is my personal information handled?",
    answer:
      "Our public pages never show contact details, exact dates of birth or private photos. As a member, you will choose who can see your photos and contact details through your privacy settings.",
    reviewNote: "The Privacy Policy is drafted at /privacy-policy; link it here once it is approved (features/legal/config.ts).",
  },
  {
    id: "account-help",
    question: "What should I do if I need help with my account?",
    answer:
      "Members sign in on the login page with their email address and password. If you've forgotten your password, or used to sign in with a code sent to your mobile, choose \"Forgot password?\" to get a link by email. Never share your password with anyone, including people who claim to be from Massil Matrimony.",
    reviewNote: "Add the real support channel once it is decided.",
  },
  {
    id: "mobile",
    question: "Can I use Massil Matrimony on my mobile phone?",
    answer:
      "Yes. The website works in any modern browser on phones, tablets and computers, with nothing to install. Text, buttons and forms are sized to be comfortable on a small screen.",
  },
  {
    id: "contact-support",
    question: "How can I contact Massil Matrimony support?",
    answer:
      "Our phone number, email address and office details will be listed on the Contact Us page, which is being prepared. We will publish them there before member registration opens.",
    reviewNote: "PLACEHOLDER: replace with the real phone, email, office address and hours.",
  },
];
