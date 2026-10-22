/**
 * The My Profile page's sections, in order: ids are the anchors set by the
 * profile editor (components/profile-editor.tsx `profileSections`). A plain
 * module so Server Components can read it (the editor is a Client Component).
 */
export const PROFILE_SECTION_TABS = [
  { id: "personal", label: "Personal" },
  { id: "about", label: "About Me" },
  { id: "career", label: "Education & Career" },
  { id: "family", label: "Family" },
  { id: "lifestyle", label: "Lifestyle" },
  { id: "preferences", label: "Partner Preferences" },
] as const;
