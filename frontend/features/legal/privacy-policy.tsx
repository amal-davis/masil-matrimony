import { A, H3, List, Owner, P, Pending, type LegalSection } from "./components/legal-document";
import { legalConfig, SERVICE_NAME } from "./config";

/**
 * The Privacy Policy, section by section. Describes only what the website and
 * API do today (checked against backend/apps and frontend/features); update it
 * whenever data collection, sharing or retention changes. Owner decisions are
 * <Pending> notes (features/legal/config.ts). Needs legal review before publication.
 */
export const privacySections: LegalSection[] = [
  {
    id: "introduction",
    title: "Introduction and scope",
    body: (
      <>
        <P>
          {SERVICE_NAME} is a matrimonial service that helps adults in India, and their families, find a suitable life
          partner. It is operated by <Owner value={legalConfig.legalName} pending="legalName" /> (&ldquo;we&rdquo;,
          &ldquo;us&rdquo;).
        </P>
        <P>
          This policy explains what personal information we collect through our website and member dashboard, why we
          collect it, who can see it, and the choices you have. It applies to members, to people who create a profile
          on behalf of a family member, and to visitors who contact us. It does not cover other websites that we link
          to.
        </P>
        <P>
          A matrimonial profile is personal by nature. Please read this policy together with our{" "}
          <A href="/terms-and-conditions">Terms &amp; Conditions</A>, and share only what you are comfortable showing
          to other members.
        </P>
      </>
    ),
  },
  {
    id: "information-we-collect",
    title: "Information we collect",
    body: (
      <>
        <P>We collect the information you, or the family member managing your profile, give us:</P>
        <H3>Account details</H3>
        <List
          items={[
            "Your name, email address and mobile number.",
            "Your password, which we store only in a scrambled (hashed) form that we cannot read back.",
            "Whether and when your email address or mobile number has been confirmed.",
          ]}
        />
        <H3>Profile and biodata</H3>
        <List
          items={[
            "Who the profile is for (yourself, a son, daughter, sibling or another relative), the display name, gender and date of birth.",
            "Height, marital status, religion, community and mother tongue.",
            "Location: country, state, district, city and native place.",
            "Education, institution, occupation, type of employment, work location and annual income.",
            "Family details: family type and values, family location, parents' occupations and siblings.",
            "Diet, hobbies, interests, languages and a short introduction written by you.",
            "Partner preferences, such as age and height range, marital status, religion, community, location, education and occupation.",
          ]}
        />
        <P>
          Apart from the details needed to create a profile (who it is for, name, gender and date of birth), most of
          these fields are optional. Religion and community can be sensitive: provide them only if you want them to be
          part of your matrimonial profile.
        </P>
        <H3>Photographs</H3>
        <P>
          The photos you upload to your profile. When a photo is uploaded we convert it to a new image file, which
          removes hidden information stored in the original file, such as the camera&apos;s location data.
        </P>
        <H3>Your activity on the service</H3>
        <List
          items={[
            "Interests you send, receive, accept or decline, and the profiles you shortlist.",
            "Notifications we show you in your dashboard.",
            "Your membership: the package, its start and end dates, and how much of any contact allowance has been used.",
            "Your privacy choices and the review status of your profile and photos.",
          ]}
        />
        <H3>Enquiries</H3>
        <P>
          If you use our contact form, we collect your name, email address, phone number and message so that our team
          can reply.
        </P>
        <H3>What we do not currently collect</H3>
        <P>
          We do not currently ask for identity documents, horoscopes or bank and card details through the website. If
          this changes, we will update this policy first and explain why the information is needed.
        </P>
      </>
    ),
  },
  {
    id: "technical-information",
    title: "Sign-in and technical information",
    body: (
      <>
        <P>To keep accounts secure and the service running, we also process:</P>
        <List
          items={[
            "Sign-in records, such as when you last signed in, and records of unsuccessful sign-in attempts and password-reset requests. These attempt records hold a coded value derived from the email address, not the address itself.",
            "Your device's IP address, which we use to limit repeated sign-in, password-reset and form submissions.",
            "Server logs that record requests to our website and API, used to find faults and investigate misuse.",
            "The cookies described in the “Cookies and similar technologies” section.",
          ]}
        />
      </>
    ),
  },
  {
    id: "how-we-use-information",
    title: "Why we use your information",
    body: (
      <>
        <P>We use personal information to:</P>
        <List
          items={[
            "create and manage your account and sign you in;",
            "build your matrimonial profile and show it to other members according to your privacy settings;",
            "suggest matches based on your profile and partner preferences;",
            "let you send, receive and respond to interests, and keep a shortlist;",
            "review profiles and photos before they are shown to other members;",
            "provide and administer membership packages, including assisted matchmaking services;",
            "send you account messages, such as password-reset links and notices that your password was changed;",
            "reply to enquiries and support requests;",
            "keep the service secure, prevent fraud and misuse, and enforce our Terms & Conditions; and",
            "meet our legal obligations.",
          ]}
        />
        <P>
          We process your information on the basis of the consent you give when you register or submit your profile,
          and where the law otherwise allows it, for example to comply with a legal obligation. You can withdraw your
          consent at any time (see &ldquo;Your choices and rights&rdquo;), but we may then be unable to keep your
          profile on the service.
        </P>
      </>
    ),
  },
  {
    id: "profile-visibility",
    title: "Who can see your profile",
    body: (
      <>
        <P>Your profile is not public. In particular:</P>
        <List
          items={[
            "A new profile is not shown to anyone until you submit it and our team has reviewed it.",
            "Approved profiles can be seen only by signed-in members, not by visitors or search engines.",
            "Other members see your profile details, but never your email address, mobile number or exact date of birth on your profile page.",
            "You can hide your profile at any time from Account Settings. Hidden profiles do not appear in matches and cannot receive new interests.",
            "You choose who can see your photos: all members, or only members whose interest you have accepted. Photos are reviewed before they are shown, and are delivered through links that stop working after a short time.",
            "Your annual income is hidden from other members unless you choose to show it.",
          ]}
        />
        <P>
          Once another member has seen your profile, we cannot control what they remember, note down or share. Only
          include information you are comfortable sharing with people you have not yet met.
        </P>
        <P>
          Some membership packages describe access to members&apos; contact numbers. That feature is not available
          yet. When it is introduced, we will update this policy to explain exactly when your contact details can be
          shared and how your consent and privacy settings apply.
        </P>
      </>
    ),
  },
  {
    id: "sharing",
    title: "When we share information",
    body: (
      <>
        <P>We share personal information only as described below:</P>
        <List
          items={[
            <>
              <strong className="font-semibold">With other members</strong>, as described in &ldquo;Who can see your
              profile&rdquo;.
            </>,
            <>
              <strong className="font-semibold">With our staff</strong>, who can see member information only as
              needed for their role, for example reviewing profiles and photos, providing assisted matchmaking, or
              answering enquiries.
            </>,
            <>
              <strong className="font-semibold">With service providers</strong> who run parts of the service for us
              and may only use the information to do so: website and database hosting (<Pending id="hosting" />),
              email delivery (<Pending id="emailProvider" />) and SMS delivery (<Pending id="smsProvider" />).
            </>,
            <>
              <strong className="font-semibold">With authorities or others</strong> where the law requires it, or
              where it is necessary to protect the safety, rights or property of our members, the public or us.
            </>,
            <>
              <strong className="font-semibold">With a new owner</strong>, if the business is reorganised, merged or
              sold, subject to the same protections described in this policy.
            </>,
          ]}
        />
        <P>
          <Pending id="dataSale" />
        </P>
      </>
    ),
  },
  {
    id: "payments",
    title: "Membership payments",
    body: (
      <>
        <P>
          Membership packages cannot currently be bought on the website, and the website does not collect card, UPI or
          bank details. Packages are arranged with our team, and we keep a record of your package and its validity.
        </P>
        <P>
          <Pending id="payments" />
        </P>
        <P>If online payments are introduced, we will update this policy before they go live.</P>
      </>
    ),
  },
  {
    id: "cookies",
    title: "Cookies and similar technologies",
    body: (
      <>
        <P>
          We use only the cookies needed for the website to work. We do not currently use analytics, advertising or
          tracking cookies.
        </P>
        <List
          items={[
            "Sign-in cookies that keep you signed in securely. They cannot be read by scripts on the page, and they are removed when you log out.",
            "A small cookie that tells the website you are signed in, so it can show the right menu.",
            "If you tick “Keep me signed in”, a cookie that keeps you signed in after you close the browser. Otherwise your sign-in ends when the browser is closed.",
            "Your browser's local storage, used to remember display choices such as whether the dashboard menu is collapsed.",
          ]}
        />
        <P>
          If our office address is shown on the Contact page with an embedded Google map, Google may set its own
          cookies when the map loads. That is governed by Google&apos;s privacy policy.
        </P>
      </>
    ),
  },
  {
    id: "security",
    title: "How we protect your information",
    body: (
      <>
        <P>We use reasonable technical and organisational safeguards, including:</P>
        <List
          items={[
            "storing passwords only in hashed form, and sending password-reset links that expire and work only once;",
            "encrypted (HTTPS) connections on the live website;",
            "keeping sign-in tokens in cookies that scripts on the page cannot read;",
            "limits on repeated sign-in attempts and password-reset requests;",
            "staff access based on role, and review of profiles and photos before they are shown; and",
            "serving photos through links that expire, rather than publicly listing them.",
          ]}
        />
        <P>
          No system is completely secure, and we cannot guarantee that information will never be accessed without
          permission. Keep your password private, and tell us straight away if you think your account has been
          misused.
        </P>
      </>
    ),
  },
  {
    id: "retention",
    title: "How long we keep information",
    body: (
      <>
        <P>
          We keep your information while your account is open and for as long as needed for the purposes in this
          policy, including resolving disputes and meeting legal, tax and accounting requirements.
        </P>
        <P>
          <Pending id="retention" />
        </P>
        <P>
          Records of unsuccessful sign-in attempts and password-reset requests are needed only for a short time and
          are deleted regularly.
        </P>
      </>
    ),
  },
  {
    id: "your-rights",
    title: "Your choices and rights",
    body: (
      <>
        <P>You can:</P>
        <List
          items={[
            "see and update most of your profile, photos, partner preferences and privacy settings in your dashboard;",
            "ask us to correct your name, gender or date of birth, which cannot be changed in the dashboard once your profile has been submitted;",
            "hide your profile at any time from Account Settings;",
            "ask for a summary of the personal information we hold about you;",
            "withdraw your consent and ask us to close your account and erase your information, subject to records we must keep by law; and",
            "raise a complaint with us (see “Contact and complaints”).",
          ]}
        />
        <P>
          To make a request, <A href="/contact">contact us</A>. We may need to confirm your identity before acting on
          it. <Pending id="deletionProcess" />
        </P>
        <P>
          You may also have rights under the Digital Personal Data Protection Act, 2023, as its provisions come into
          force, including the right to nominate someone to act for you and to complain to the Data Protection Board of
          India.
        </P>
      </>
    ),
  },
  {
    id: "communications",
    title: "Emails and other messages",
    body: (
      <>
        <P>
          We send service messages that you cannot switch off while you have an account, because they are needed to
          run it: for example password-reset links and notices that your password has changed. Updates about
          interests and your profile are shown as notifications in your dashboard.
        </P>
        <P>
          We do not currently send promotional emails or messages. <Pending id="marketing" />
        </P>
      </>
    ),
  },
  {
    id: "third-parties",
    title: "Other websites and services",
    body: (
      <P>
        Our website may link to or embed other services, such as maps and social media pages. Those services are run
        by other companies under their own privacy policies, and we are not responsible for how they handle your
        information.
      </P>
    ),
  },
  {
    id: "eligibility",
    title: "Age and eligibility",
    body: (
      <>
        <P>
          {SERVICE_NAME} is only for adults who are of legal age to marry in India: at least 18 years for women and 21
          years for men. We do not knowingly create profiles for, or collect information about, anyone below these
          ages. A parent or relative may manage a profile for an adult family member, but only with that person&apos;s
          knowledge and agreement.
        </P>
        <P>If you believe we hold information about a child, please contact us and we will remove it.</P>
      </>
    ),
  },
  {
    id: "changes",
    title: "Changes to this policy",
    body: (
      <P>
        We will update this policy when our service or the law changes. The date at the top shows when it was last
        changed. If we make an important change, we will tell members through the website or by email before it takes
        effect.
      </P>
    ),
  },
  {
    id: "contact",
    title: "Contact and complaints",
    body: (
      <>
        <P>For privacy questions, requests or complaints, contact us:</P>
        <List
          items={[
            <>
              Business name: <Owner value={legalConfig.legalName} pending="legalName" />
            </>,
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
        <P>
          You can also reach us through our <A href="/contact">Contact page</A>.
        </P>
      </>
    ),
  },
];
