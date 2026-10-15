import type { HighlightedProfile } from "./types";

/**
 * TEMPORARY, FICTIONAL demonstration profiles for building the homepage
 * before the profiles API exists. These are not real people and have no
 * photos on purpose (the card shows its placeholder portrait).
 *
 * Remove this file once GET /profiles/highlighted/ is implemented; see api.ts.
 */
export const demoProfiles: HighlightedProfile[] = [
  {
    id: "demo-1",
    profileCode: "DEMO001",
    displayName: "Anjali",
    age: 25,
    education: "M.Sc.",
    location: { district: "Thrissur", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-2",
    profileCode: "DEMO002",
    displayName: "Arjun",
    age: 29,
    education: "B.Tech",
    location: { district: "Ernakulam", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-3",
    profileCode: "DEMO003",
    displayName: "Meera",
    age: 27,
    education: "MBA",
    location: { district: "Kottayam", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-4",
    profileCode: "DEMO004",
    displayName: "Rahul",
    age: 31,
    education: "M.Com",
    location: { district: "Kozhikode", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-5",
    profileCode: "DEMO005",
    displayName: "Nimisha",
    age: 26,
    education: "B.Sc. Nursing",
    location: { district: "Palakkad", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-6",
    profileCode: "DEMO006",
    displayName: "Joel",
    age: 30,
    education: "MCA",
    location: { district: "Thiruvananthapuram", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-7",
    profileCode: "DEMO007",
    displayName: "Lakshmi",
    age: 24,
    education: "BDS",
    location: { district: "Alappuzha", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-8",
    profileCode: "DEMO008",
    displayName: "Aswin",
    age: 28,
    education: "B.Arch",
    location: { district: "Kannur", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-9",
    profileCode: "DEMO009",
    displayName: "Sneha",
    age: 26,
    education: "M.Tech",
    location: { district: "Kollam", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-10",
    profileCode: "DEMO010",
    displayName: "Faisal",
    age: 30,
    education: "MBBS",
    location: { district: "Malappuram", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-11",
    profileCode: "DEMO011",
    displayName: "Diya",
    age: 25,
    education: "B.Com",
    location: { district: "Pathanamthitta", state: "Kerala" },
    photo: null,
  },
  {
    id: "demo-12",
    profileCode: "DEMO012",
    displayName: "Rohan",
    age: 32,
    education: "Ph.D.",
    location: { district: "Idukki", state: "Kerala" },
    photo: null,
  },
];
