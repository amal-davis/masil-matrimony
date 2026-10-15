---
name: Maasil Matrimony
description: Where two families become one. A trusted matrimonial service for Malayali families.
colors:
  wine-900: "#1f050b"
  wine-800: "#2a0810"
  wine-600: "#4b0f1e"
  gold: "#d2a54a"
  gold-soft: "#e9d5a0"
  ivory: "#f7eedd"
  white: "#ffffff"
  mist: "#f8f4f4"
  ink: "#241a1c"
  ink-muted: "#5e4f53"
  field-line: "#8a7b7f"
  hairline: "#e5dadc"
  success: "#2e6b45"
  danger: "#a3261f"
typography:
  display:
    fontFamily: "Cormorant Garamond, Cormorant, Garamond, Times New Roman, serif"
    fontSize: "clamp(2.5rem, 6vw, 4.5rem)"
    fontWeight: 500
    lineHeight: 1.05
    letterSpacing: "0.01em"
  headline:
    fontFamily: "Cormorant Garamond, Cormorant, Garamond, Times New Roman, serif"
    fontSize: "clamp(1.875rem, 4vw, 2.75rem)"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "0.01em"
  tagline:
    fontFamily: "Cormorant Garamond, Cormorant, Garamond, Times New Roman, serif"
    fontSize: "clamp(1.4rem, 4.6vw, 2rem)"
    fontWeight: 400
    lineHeight: 1.3
  title:
    fontFamily: "Jost, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 500
    lineHeight: 1.35
  body:
    fontFamily: "Jost, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Jost, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
  wordmark-kicker:
    fontFamily: "Jost, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.62em"
rounded:
  sm: "6px"
  md: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  2xl: "64px"
  3xl: "96px"
components:
  button-primary:
    backgroundColor: "{colors.wine-600}"
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "14px 28px"
    height: "52px"
  button-primary-hover:
    backgroundColor: "{colors.wine-800}"
    textColor: "{colors.white}"
  button-gold:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.wine-900}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "14px 28px"
    height: "52px"
  button-gold-hover:
    backgroundColor: "{colors.gold-soft}"
    textColor: "{colors.wine-900}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.wine-600}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "14px 28px"
    height: "52px"
  input-field:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "12px 16px"
    height: "52px"
  nav-bar:
    backgroundColor: "{colors.wine-800}"
    textColor: "{colors.ivory}"
    height: "72px"
  profile-card:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "24px"
  advisor-band:
    backgroundColor: "{colors.wine-800}"
    textColor: "{colors.ivory}"
    padding: "64px 24px"
---

# Design System: Maasil Matrimony

## 1. Overview

**Creative North Star: "The Wine-and-Gold Invitation, Opened"**

The coming-soon page at maasilmatrimony.com is a sealed invitation: deep wine, a gold monogram, an invitation-card border and the line *"Where two families become one."* The website is that invitation opened. The wine and gold stay at the edges (the header, the hero, the advisor band and the footer) like the cover of a card. Inside, the pages are clear white, so a parent can read, search and fill in forms comfortably.

PRODUCT.md asks for a brand that is **trusted, warm, rooted** and readable *"by a 55-year-old on a mid-range Android phone in daylight first."* So richness lives in colour, the monogram and the serif headlines, never in ornament. The system explicitly rejects **generic SaaS landing pages** (gradient blobs, metric heroes, identical icon-card grids), **wedding-card kitsch** (heavy gold foil, mandala borders, ornate script everywhere) and the **dating-app vibe** (swipe mechanics, flirtatious tone, neon).

Layout is information-rich but orderly, following nestmatrimony.com's content model (registration and quick search above the fold, trust proof, an assisted-service band, browse-by-community) with clearer hierarchy and far less repetition. Content sits in a 1200px-max container with generous vertical rhythm (64–96px between sections on desktop, 40–64px on mobile). Motion is gentle: the coming-soon page's soft staggered rise plays once, on the hero only.

**Key Characteristics:**
- Wine frame, white content: wine bands open and close the page and mark the assisted-service moment; everything you read or fill in sits on white.
- Gold is jewellery: logo, hairlines and small accents on wine. Never text on white.
- Cormorant Garamond for display, Jost for everything you actually read.
- One signature moment each: the invitation-card frame around the hero and the interlocking rings once under the tagline.
- Large type, high contrast and 48px+ tap targets throughout.

## 2. Colors: The Wine-and-Gold Palette

A committed two-colour identity, deep wine and burnished gold, taken directly from the coming-soon page and balanced by pure white for everything functional.

### Primary
- **Maasil Wine** (wine-800): the brand's ground colour. Header, hero, advisor band and footer backgrounds, and the browser `theme-color`. Ivory text on it measures 16:1.
- **Deep Wine** (wine-900): the darkest edge. Hero vignette, footer base, and text placed on gold buttons (8.5:1).
- **Wine Velvet** (wine-600): the action colour on white. Primary buttons, links, headings on white sections, focus rings on white. It measures 15:1 on white and 13.9:1 on mist.

### Secondary
- **Monogram Gold** (gold): the colour of the MM monogram. Used on wine only: the logo, 1px hairlines, the hero frame, the rings divider, the gold button and small accent text (8.1:1 on wine-800).
- **Soft Gold** (gold-soft): secondary text and taglines on wine (12.7:1), and the gold button's hover state.

### Neutral
- **Ivory** (ivory): primary text on wine surfaces. Never used as a page or section background.
- **White** (white): the reading surface for every content section, form and card.
- **Mist** (mist): an alternate section background on white pages, tinted faintly toward wine rather than warm cream. Use it to separate adjacent white sections.
- **Ink** (ink): body text and headings on white (16.9:1).
- **Ink Muted** (ink-muted): secondary text, helper text and metadata on white (7.7:1) or mist (7.1:1). This is the lightest text colour allowed on light surfaces.
- **Field Line** (field-line): input borders and checkbox outlines (4:1 on white, above the 3:1 non-text minimum).
- **Hairline** (hairline): decorative dividers and card borders on white. Never the only boundary of an interactive control.
- **Success** (success) / **Danger** (danger): form validation and status messages, always paired with an icon and text, never colour alone.

### Named Rules
**The Gold Is Jewellery Rule.** Gold appears only on wine surfaces and never covers more than about 10% of any screen. Gold text on white is prohibited: it measures 2.3:1 and fails WCAG.

**The Read It On White Rule.** Anything longer than two sentences, and every form field, sits on white or mist. Wine surfaces carry headlines, short supporting lines and calls to action only.

**The No Cream Rule.** Ivory is a text colour, not a background. Light surfaces are pure white or wine-tinted mist, never cream, sand or parchment.

## 3. Typography

**Display Font:** Cormorant Garamond (with Garamond, Times New Roman, serif)
**Body Font:** Jost (with Helvetica Neue, Arial, sans-serif)

**Character:** A high-contrast, old-style Garamond gives the brand its ceremony and dignity. A clean geometric sans carries every word that must be read quickly. The pairing is the same one used on the coming-soon page, so the brand reads continuously from that page to this site.

### Hierarchy
- **Display** (Cormorant Garamond 500, clamp(2.5rem, 6vw, 4.5rem), line-height 1.05): the hero headline and the "Maasil" wordmark only. One per page.
- **Headline** (Cormorant Garamond 500, clamp(1.875rem, 4vw, 2.75rem), line-height 1.15): section headings. `text-wrap: balance`.
- **Tagline** (Cormorant Garamond italic 400, clamp(1.4rem, 4.6vw, 2rem), line-height 1.3): the brand line *"Where two families become one."* and at most one supporting quote per page (e.g. a success story pull-quote).
- **Title** (Jost 500, 1.25rem, line-height 1.35): card titles, form section titles and profile names.
- **Body** (Jost 400, 1.125rem / 18px, line-height 1.65): all running text, max 68ch per line. `text-wrap: pretty`. Body text never goes below 16px, even on mobile.
- **Label** (Jost 500, 0.9375rem / 15px, letter-spacing 0.01em): buttons, form labels, nav links, chips.
- **Wordmark Kicker** (Jost 400, 0.8125rem, letter-spacing 0.62em, uppercase, gold): exclusively the word "MATRIMONY" beneath "Maasil" in the logo lockup.

### Named Rules
**The Serif Is For Speaking Up Rule.** Cormorant Garamond is used only at 24px and above. Its thin strokes vanish at small sizes on low-end screens, so labels, forms, body text and anything under 24px use Jost.

**The One Kicker Rule.** Wide-tracked uppercase text belongs to the wordmark alone. No uppercase eyebrow labels above section headings.

**The Malayalam-Ready Rule.** Layouts must tolerate 30–40% longer strings and taller glyphs. When Malayalam ships, pair with Noto Serif Malayalam (display) and Noto Sans Malayalam (body), and keep line-height at 1.65 or more for body text.

## 4. Elevation

The system is flat and tonal. Depth comes from the contrast between wine bands and white sections, from mist alternating with white, and from 1px hairlines, not from stacked shadows. Shadows appear in only three places: the gold monogram on wine (as on the coming-soon page), the sticky header once the page scrolls, and floating layers (dropdowns, dialogs, the mobile menu).

### Shadow Vocabulary
- **Monogram Lift** (`filter: drop-shadow(0 18px 28px rgba(0, 0, 0, 0.45))`): the gold MM logo on wine surfaces only.
- **Header Settle** (`box-shadow: 0 1px 0 rgba(210, 165, 74, 0.25), 0 8px 24px rgba(31, 5, 11, 0.18)`): the sticky wine header after scroll; the gold hairline doubles as its bottom edge.
- **Float** (`box-shadow: 0 12px 32px rgba(36, 26, 28, 0.14)`): dropdowns, dialogs and popovers above white content.

### Named Rules
**The Flat-At-Rest Rule.** Cards and panels on white have no shadow at rest; a hairline border defines them. Hover may darken the border to field-line, never lift the card.

## 5. Components

Formal and steady, like good stationery: modest corners, firm edges, generous size. Every interactive control has a target of at least 48×48px, with a visible focus ring of 2px wine-600 on light surfaces and 2px gold on wine surfaces, offset by 2px.

### Buttons
- **Shape:** gently squared corners (6px). No pill buttons.
- **Primary (on white):** wine-600 fill, white Jost 500 label, 52px tall, 14px 28px padding.
- **Gold (on wine only):** gold fill, wine-900 label. The main call to action inside wine bands ("Register free", "Request a callback").
- **Secondary:** white fill, 1.5px wine-600 border, wine-600 label. On wine, the inverse is transparent with a 1.5px gold border and gold-soft label.
- **Hover / Focus:** colour shifts over 180ms using ease-out-quart (`cubic-bezier(0.25, 1, 0.5, 1)`). No lift, no scale, no glow. Disabled buttons drop to 50% opacity and keep their label.

### Inputs / Fields
- **Style:** white field, 1px field-line border, 6px radius, 52px tall, 18px Jost text. Labels always sit visibly above the field; placeholders are examples, never labels.
- **Focus:** the border becomes 2px wine-600, with no glow.
- **Error / Disabled:** errors show a danger border, an icon and a message below in danger text, linked with `aria-describedby`. Disabled fields use a mist fill with ink-muted text.
- **Selects and toggles:** the bride/groom choice is a two-option segmented control (wine-600 fill for the selected option), not a dropdown.

### Cards / Containers
- **Corner Style:** softly rounded (12px).
- **Background:** white on mist sections, or white with a hairline border on white sections.
- **Shadow Strategy:** flat at rest (see Elevation).
- **Internal Padding:** 24px mobile, 32px desktop.
- **Profile cards:** photo (4:5, 12px top corners, blurred or monogram placeholder when private), first name in Title, then age · height · education · district in Body/ink-muted. No contact details, ever.

### Navigation
- **Header:** wine-800 bar, 72px tall, sticky. Gold MM monogram (40px) and the "Maasil" wordmark on the left. Ivory Jost 500 links with a gold 1px underline on hover and on the current page. Login is a gold-bordered secondary button and Register is a gold button on the right.
- **Mobile:** a hamburger (48px target) opens a full-width wine panel with 56px-tall links; Register and Request a callback are pinned at the bottom of the panel.
- **Footer:** wine-900 with a 1px gold hairline on top. Ivory links, gold-soft section titles in Title style, and "© Maasil Matrimony" in ivory at no less than 50% opacity (4.6:1 minimum).

### Hero Invitation Frame (signature)
The coming-soon page's double gold hairline with corner diamonds frames the hero: an outer 1px border in gold at 55% opacity, an inner 1px border at 22% opacity inset 6px, and 11px gold diamonds on each corner. Used once per site, in the home page hero. Inside it: monogram, display headline, the tagline in Tagline style, the interlocking-rings divider (148×24, gold) and the quick search or registration entry.

### Interlocking Rings Divider (signature)
Two overlapping 9px-radius gold circles with 54px hairlines on either side. Appears exactly once, under the hero tagline. It is not a general section divider.

### Advisor Band (signature)
A full-width wine-800 band introducing the assisted service: a headline in Headline style in ivory, one or two lines of gold-soft body text, and a gold "Request a callback" button with a secondary "Call us" link. It appears once per page at most and gives the assisted path equal weight with self-registration.

### Motion
The hero contents rise 14px and fade in over 1.1s (`cubic-bezier(0.2, 0.7, 0.2, 1)`), staggered 150–200ms apart, and the frame fades in over 1.6s, exactly as on the coming-soon page. Content is visible by default and the animation only enhances it. Everything else uses 180ms colour and opacity transitions. Under `prefers-reduced-motion: reduce`, all entrances are removed and transitions become instant.

## 6. Do's and Don'ts

### Do:
- **Do** use wine-800 for the header, hero, advisor band and footer, and pure white or mist for every content section.
- **Do** keep gold on wine only: logo, 1px hairlines, the hero frame, the rings divider, gold buttons and short accent text.
- **Do** set body text in Jost at 18px or larger with line-height 1.65, in ink on white.
- **Do** make every tap target at least 48×48px and every form field 52px tall with a visible label above it.
- **Do** put registration and quick search in the hero and the advisor band once per page, so self-serve and assisted service carry equal weight.
- **Do** show trust with real, consistent facts (the verification process, privacy controls, an office address, a real phone number).
- **Do** use the gold monogram with its drop shadow on wine surfaces.

### Don't:
- **Don't** set gold text on white or mist (2.3:1 fails WCAG).
- **Don't** use ivory, cream, sand or parchment as a background. Light surfaces are white (#ffffff) or mist (#f8f4f4).
- **Don't** use Cormorant Garamond below 24px or for body text, labels, buttons or form fields.
- **Don't** build **generic SaaS landing pages**: no gradient blobs, no metric heroes ("5 Lakh+" as a giant stat block), no identical icon-card feature grids.
- **Don't** drift into **wedding-card kitsch**: no heavy gold foil, mandala borders or ornate script fonts, and no repeating the invitation frame or rings beyond their one signature appearance.
- **Don't** borrow the **dating-app vibe**: no swipe mechanics, playful or flirtatious copy, or neon accents.
- **Don't** put uppercase tracked eyebrow labels above section headings; wide tracking belongs to the wordmark alone.
- **Don't** use side-stripe borders (`border-left` thicker than 1px) as accents on cards or callouts.
- **Don't** use pill-shaped buttons, gradient text or glassmorphism.
- **Don't** show contact details, exact birth dates or private photos on any public surface.
- **Don't** animate anything that delays reading, and never ship an animation without a reduced-motion alternative.
