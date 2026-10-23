import { membershipPackages } from "@/features/packages/packages";

import { A, List, Owner, P, Pending, type LegalSection } from "./components/legal-document";
import { legalConfig, SERVICE_NAME } from "./config";
import { packagePriceSummary, packageTitle } from "./package-summary";

/**
 * The Terms & Conditions, section by section. Describes only the features that
 * exist today and says plainly which package features are still to come.
 * Package names, fees and validity come from features/packages/packages.ts.
 * Owner decisions are <Pending> notes (features/legal/config.ts). Needs legal
 * review before publication.
 */
export const termsSections: LegalSection[] = [
  {
    id: "acceptance",
    title: "About these terms",
    body: (
      <>
        <P>
          These terms apply to your use of the {SERVICE_NAME} website, member dashboard and related services (the
          &ldquo;service&rdquo;), operated by <Owner value={legalConfig.legalName} pending="legalName" />{" "}
          (&ldquo;we&rdquo;, &ldquo;us&rdquo;).
        </P>
        <P>
          By creating an account, managing a profile or using the service, you agree to these terms and to our{" "}
          <A href="/privacy-policy">Privacy Policy</A>. If you do not agree, please do not use the service. Assisted
          matchmaking packages are also covered by the separate service agreement you sign with us.
        </P>
      </>
    ),
  },
  {
    id: "our-service",
    title: "What we do, and what we cannot promise",
    body: (
      <>
        <P>
          {SERVICE_NAME} helps people and their families find and contact prospective life partners. We provide tools
          and, in some packages, personal assistance from our team.
        </P>
        <P>
          We facilitate introductions; we do not arrange or guarantee marriages. We cannot promise that you will find a
          suitable partner, that a match will be compatible, that another member will respond, or that a marriage will
          take place. Decisions about whom to meet and marry are entirely yours and your family&apos;s.
        </P>
      </>
    ),
  },
  {
    id: "eligibility",
    title: "Who can use the service",
    body: (
      <>
        <P>To use the service, the person the profile is for must:</P>
        <List
          items={[
            "be of legal age to marry in India: at least 18 years for women and 21 years for men;",
            "be legally free to marry, and seeking marriage; and",
            "not be barred by law from using the service.",
          ]}
        />
        <P>
          A parent, sibling or relative may create and manage a profile for an adult family member, but only with that
          person&apos;s knowledge and agreement. Whoever manages the profile accepts these terms on their behalf and is
          responsible for its accuracy.
        </P>
      </>
    ),
  },
  {
    id: "accounts",
    title: "Your account",
    body: (
      <>
        <P>
          You can register online, or our team can create your account for you. Each account must use a working email
          address and mobile number that belong to you or to the family member managing the profile, and you sign in
          with that email address and your password.
        </P>
        <List
          items={[
            "Keep your account details accurate and up to date.",
            "Keep your password private. Do not share your account or let others use it.",
            "You are responsible for activity on your account. Tell us straight away if you think someone else has accessed it, and reset your password.",
          ]}
        />
      </>
    ),
  },
  {
    id: "profiles",
    title: "Profiles and the information you provide",
    body: (
      <>
        <P>
          You must give true, current and complete information about the person the profile is for, including marital
          status, age, education, occupation and family details. Do not hide facts that a prospective partner would
          reasonably expect to know.
        </P>
        <P>
          New profiles are reviewed by our team before other members can see them. We may ask you to correct details,
          and we may decline a profile that appears inaccurate or breaks these terms. Once a profile has been
          submitted, the name, gender and date of birth can only be changed by contacting us.
        </P>
        <P>
          You remain responsible for the information in your profile. You give us permission to store it, show it to
          other members according to your privacy settings, and use it to suggest matches, for as long as your profile
          is on the service.
        </P>
      </>
    ),
  },
  {
    id: "verification",
    title: "Verification and its limits",
    body: (
      <>
        <P>
          Our review of profiles and photos is a check for suitability and obvious problems. It is not a full
          background check, and we do not confirm every detail members provide, such as identity, education,
          employment, income, marital status or family background.
        </P>
        <P>
          <Pending id="verification" />
        </P>
        <P>
          Before making any commitment, you and your family should independently confirm the details of any person you
          are considering, and meet in safe, public settings.
        </P>
      </>
    ),
  },
  {
    id: "acceptable-use",
    title: "Acceptable use",
    body: (
      <>
        <P>You must not:</P>
        <List
          items={[
            "create a fake profile, impersonate someone, or misrepresent your age, marital status or other details;",
            "use the service for dating that is not aimed at marriage, or for any commercial purpose such as advertising, recruitment or selling;",
            "harass, threaten, insult or discriminate against other members, or send obscene or abusive content;",
            "ask other members for money, gifts or financial information, or attempt any kind of fraud;",
            "copy, collect or publish other members' information or photos, or share them outside the service;",
            "upload content that you do not have the right to share, or that is unlawful, offensive or sexually explicit;",
            "use automated tools to access the service, or try to get around its security or limits; or",
            "use the service in any way that breaks the law.",
          ]}
        />
        <P>
          Never send money to someone you have met through the service, whatever reason they give. We will never ask
          for your password.
        </P>
      </>
    ),
  },
  {
    id: "photos-and-content",
    title: "Photos and other content",
    body: (
      <>
        <P>
          Photos must be recent, clearly show the person the profile is for, and be yours to share. Photos of other
          people, children, celebrities, or images that are misleading or inappropriate are not allowed.
        </P>
        <P>
          Photos are reviewed before other members can see them, and we may decline or remove any photo or other
          content that breaks these terms. You keep ownership of your photos and content; you give us permission to
          store them, adapt them for display, and show them to other members according to your privacy settings.
        </P>
      </>
    ),
  },
  {
    id: "features",
    title: "Matches, interests and other features",
    body: (
      <>
        <P>Members can currently:</P>
        <List
          items={[
            "see match suggestions based on their profile and partner preferences;",
            "view the profiles of other members, as their privacy settings allow;",
            "send interests, and accept or decline interests they receive;",
            "shortlist profiles; and",
            "control who can see their profile and photos.",
          ]}
        />
        <P>
          Some features described in our membership packages, including personal messaging, access to members&apos;
          contact numbers, &ldquo;who viewed my profile&rdquo;, and advanced search, are not available yet. They will
          be offered only when they are launched, and their use will be subject to the privacy settings and consent of
          the members concerned. We will update these terms when they are introduced.
        </P>
        <P>
          Match suggestions are generated from the information members provide. They are not a recommendation or an
          assessment of compatibility.
        </P>
      </>
    ),
  },
  {
    id: "privacy",
    title: "Privacy",
    body: (
      <P>
        Our <A href="/privacy-policy">Privacy Policy</A> explains how we collect, use and share personal information,
        and the choices you have. Information you see about other members is for your personal matrimonial search only.
        You must not use it for any other purpose.
      </P>
    ),
  },
  {
    id: "memberships",
    title: "Memberships and fees",
    body: (
      <>
        <P>
          Registering and creating a profile is free. Paid packages add features or personal assistance. The current
          packages and fees are:
        </P>
        <List
          items={membershipPackages.map((pkg) => (
            <>
              <strong className="font-semibold">{packageTitle(pkg)}</strong>: {packagePriceSummary(pkg)}
            </>
          ))}
        />
        <P>
          The full list of benefits for each package is on our <A href="/our-packages">Membership page</A>. Benefits
          marked there as subject to availability depend on service and platform availability, and features that are
          not yet available (see &ldquo;Matches, interests and other features&rdquo;) are not included until they are
          launched.
        </P>
        <P>
          <Pending id="pricingChanges" />
        </P>
      </>
    ),
  },
  {
    id: "payments-refunds",
    title: "Payments, cancellations, refunds and renewals",
    body: (
      <>
        <P>
          Packages cannot currently be bought on the website. They are arranged with our team, and a package starts
          when our team activates it. Cancellations, refunds and payment problems are handled under our{" "}
          <A href="/refund-policy">Refund &amp; Cancellation Policy</A>, and how memberships are delivered is described
          in our <A href="/shipping-policy">Shipping &amp; Delivery Policy</A>.
        </P>
        <List
          items={[
            <>
              Payment: <Pending id="payments" />
            </>,
            <>
              Cancellations and refunds: <Pending id="refunds" />
            </>,
            <>
              Renewals and expiry: <Pending id="renewals" />
            </>,
          ]}
        />
      </>
    ),
  },
  {
    id: "assisted-services",
    title: "Assisted and at-home matchmaking",
    body: (
      <>
        <P>
          The Platinum (assisted matchmaking) and Royal (at-home matchmaking) packages include personal help from our
          team. The details of that help, including service hours, home visits, travel arrangements, the number of
          profiles shortlisted, and any other limits, are set out in the service agreement you sign for the package. If
          that agreement and these terms conflict on those details, the agreement applies.
        </P>
        <P>
          <Pending id="assistedScope" />
        </P>
        <P>
          Our team will share your information with prospective matches and their families only with your agreement
          and in line with your privacy settings. Personal assistance does not guarantee a match or a marriage.
        </P>
      </>
    ),
  },
  {
    id: "safety",
    title: "Safety and reporting concerns",
    body: (
      <>
        <P>
          Take care when sharing personal details and meeting people. Talk to your family, meet in public places, and
          stop contact if anything feels wrong.
        </P>
        <P>
          If a member behaves inappropriately, asks for money, or appears to be using a fake profile,{" "}
          <A href="/contact">contact us</A> with their profile ID. In-app reporting and blocking are not available yet.
          Meanwhile, you can decline interests and hide your profile from Account Settings at any time. If you are in
          danger or have been defrauded, contact the police as well.
        </P>
      </>
    ),
  },
  {
    id: "suspension",
    title: "Suspending or closing accounts",
    body: (
      <>
        <P>
          You can hide your profile at any time, or ask us to close your account by contacting us. Closing an account
          does not by itself entitle you to a refund (see &ldquo;Payments, cancellations, refunds and renewals&rdquo;).
        </P>
        <P>
          We may suspend, hide or close a profile or account if we reasonably believe it breaks these terms, is
          inaccurate, puts other members at risk, or if the law requires it. Where appropriate, we will tell you why
          and give you a chance to respond.
        </P>
      </>
    ),
  },
  {
    id: "availability",
    title: "Availability of the service",
    body: (
      <>
        <P>
          We work to keep the service available and accurate, but it is provided as it is and as available. It may
          sometimes be interrupted for maintenance, updates or reasons outside our control, and features may change
          over time. We are not responsible for what members say or do, on or off the service.
        </P>
        <P>
          <Pending id="liability" />
        </P>
      </>
    ),
  },
  {
    id: "intellectual-property",
    title: "Our name and content",
    body: (
      <P>
        The {SERVICE_NAME} name, logo, website design and our own text and images belong to us or our licensors. You may
        not copy, reuse or adapt them without our written permission. Content that members add remains theirs, as
        described in &ldquo;Photos and other content&rdquo;.
      </P>
    ),
  },
  {
    id: "third-parties",
    title: "Other websites and services",
    body: (
      <P>
        The service may link to or include services run by others, such as maps and social media. We do not control
        them and are not responsible for their content or practices; their own terms apply.
      </P>
    ),
  },
  {
    id: "complaints",
    title: "Complaints and contact",
    body: (
      <>
        <P>
          If you have a complaint about the service or about another member, please <A href="/contact">contact us</A>{" "}
          first so we can try to resolve it.
        </P>
        <List
          items={[
            <>
              Email: <Owner value={legalConfig.email} pending="email" />
            </>,
            <>
              Address: <Owner value={legalConfig.address?.join(", ")} pending="address" />
            </>,
            <>
              Grievance Officer:{" "}
              {legalConfig.grievanceOfficer ? (
                `${legalConfig.grievanceOfficer.name}, ${legalConfig.grievanceOfficer.designation}, ${legalConfig.grievanceOfficer.email}`
              ) : (
                <Pending id="grievanceOfficer" />
              )}
            </>,
          ]}
        />
      </>
    ),
  },
  {
    id: "law",
    title: "Governing law and disputes",
    body: (
      <P>
        <Pending id="governingLaw" />
      </P>
    ),
  },
  {
    id: "changes",
    title: "Changes to these terms",
    body: (
      <P>
        We may update these terms when our service or the law changes. The date at the top shows when they were last
        changed. If we make an important change, we will tell members through the website or by email before it takes
        effect. Continuing to use the service after that means you accept the updated terms.
      </P>
    ),
  },
];
