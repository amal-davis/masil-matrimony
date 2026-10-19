import type { HighlightedProfile } from "../types";

/** Warm Indian skin tones, light to deep. */
const skinTones = ["#e6b88f", "#d39f73", "#bf855a", "#a86d45", "#8c5636"];
const hairColours = ["#1b1311", "#271a15", "#33221a"];
/** Blouse and saree colours for women; shirt or kurta colours for men. */
const womenAttire = [
  { blouse: "#8f2f3e", drape: "#c9962b" },
  { blouse: "#1f6b66", drape: "#d2a54a" },
  { blouse: "#6b3a7a", drape: "#e3b75c" },
  { blouse: "#a3402f", drape: "#2f6b4a" },
  { blouse: "#2c4f7c", drape: "#d8a64a" },
];
const CREAM_SHIRT = "#f4ecdc";
const menAttire = [CREAM_SHIRT, "#2b3a55", "#5f1c29", "#9db4c8", "#3f5f4a"];
/** Weighted: a moustache is the most common look. */
const facialHairStyles = ["none", "moustache", "moustache", "beard"] as const;

/** FNV-1a with a final mix, so ids that differ by one character still spread out. */
function hash(text: string) {
  let value = 2166136261;
  for (let i = 0; i < text.length; i++) {
    value ^= text.charCodeAt(i);
    value = Math.imul(value, 16777619);
  }
  value ^= value >>> 15;
  value = Math.imul(value, 0x2c1b3c6d);
  value ^= value >>> 12;
  return value >>> 0;
}

/**
 * Illustrated portrait used when a profile has no public photo. Not a picture
 * of a real person: each feature is chosen from the profile id, so a card is
 * stable across renders and the grid stays varied.
 */
export function ProfileAvatar({ profile }: { profile: Pick<HighlightedProfile, "id" | "gender"> }) {
  const choose = <T,>(list: readonly T[], trait: string) => list[hash(`${profile.id}:${trait}`) % list.length];
  const skin = choose(skinTones, "skin");
  const hair = choose(hairColours, "hair");

  return (
    <div className="absolute inset-0 flex items-end justify-center bg-gradient-to-b from-mist to-brand-100">
      <svg aria-hidden="true" viewBox="14 14 92 136" className="h-[95%] w-auto">
        {profile.gender === "female" ? (
          <Woman skin={skin} hair={hair} attire={choose(womenAttire, "attire")} longHair={choose([true, false], "hairstyle")} />
        ) : (
          <Man
            skin={skin}
            hair={hair}
            shirt={choose(menAttire, "attire")}
            sidePart={choose([true, false], "hairstyle")}
            facialHair={choose(facialHairStyles, "fh")}
          />
        )}
      </svg>
      <span className="sr-only">No public photo</span>
    </div>
  );
}

type FaceProps = { skin: string; hair: string };

const SHOULDERS = "M10 150c1-33 20-55 50-57 30 2 49 24 50 57Z";
const NECK = "M52 78h16v17q-8 5-16 0Z";
const NECK_SHADOW = "M52 84q8 5 16 0v4q-8 5-16 0Z";

/** Ears, head, brows, eyes and nose shared by both portraits. */
function Face({ skin, hair }: FaceProps) {
  return (
    <>
      <ellipse cx="40" cy="62" rx="3.6" ry="5.6" fill={skin} />
      <ellipse cx="80" cy="62" rx="3.6" ry="5.6" fill={skin} />
      <ellipse cx="60" cy="60" rx="20" ry="24" fill={skin} />
      <path
        d="M48 54.5q4-2.6 8 0M64 54.5q4-2.6 8 0"
        stroke={hair}
        strokeWidth="1.7"
        strokeLinecap="round"
        fill="none"
      />
      <ellipse cx="52" cy="61" rx="2.1" ry="2.4" fill="#22160f" />
      <ellipse cx="68" cy="61" rx="2.1" ry="2.4" fill="#22160f" />
      <circle cx="52.7" cy="60.2" r=".7" fill="#fff" fillOpacity=".8" />
      <circle cx="68.7" cy="60.2" r=".7" fill="#fff" fillOpacity=".8" />
      <path
        d="M58.6 69.5q1.4 1.1 2.8 0"
        stroke="#000"
        strokeOpacity=".22"
        strokeWidth="1.3"
        strokeLinecap="round"
        fill="none"
      />
    </>
  );
}

function Woman({
  skin,
  hair,
  attire,
  longHair,
}: FaceProps & { attire: (typeof womenAttire)[number]; longHair: boolean }) {
  return (
    <>
      {/* Long hair over the shoulders, or a bun with a string of jasmine. */}
      {longHair ? (
        <path
          d="M37 62c-2-23 9-37 23-37s25 14 23 37c-1 15 3 30 9 43-9 5-19 4-25-3H53c-6 7-16 8-25 3 6-13 10-28 9-43Z"
          fill={hair}
        />
      ) : (
        <circle cx="60" cy="31" r="11" fill={hair} />
      )}

      {/* Blouse, then the saree drape over the right shoulder with a gold border. */}
      <path d={SHOULDERS} fill={attire.blouse} />
      <path d="M67 95c17 3 31 16 37 35l4 20H86c-3-21-9-40-19-55Z" fill={attire.drape} />
      <path d="M67 95c10 15 16 34 19 55" stroke="#f2d48a" strokeWidth="2" fill="none" />

      <path d={NECK} fill={skin} />
      <path d={NECK_SHADOW} fill="#000" fillOpacity=".08" />
      {/* Necklace with a small pendant. */}
      <path d="M50 92q10 9 20 0" stroke="#d2a54a" strokeWidth="1.8" fill="none" />
      <circle cx="60" cy="98.5" r="2.2" fill="#d2a54a" />

      <Face skin={skin} hair={hair} />
      <circle cx="47" cy="69" r="3.4" fill="#e0675a" fillOpacity=".16" />
      <circle cx="73" cy="69" r="3.4" fill="#e0675a" fillOpacity=".16" />
      <path d="M54 75.5q6 4.6 12 0" stroke="#8f2f3e" strokeWidth="1.9" strokeLinecap="round" fill="none" />

      {/* Centre-parted hair framing the face. */}
      <path
        d="M38.5 63c-1.5-21 8-34 21.5-34s23 13 21.5 34c-3-11-9-18-16.5-20.5L60 47.5l-5-5C47.5 45 41.5 52 38.5 63Z"
        fill={hair}
      />

      {/* Jasmine tucked beside the bun. */}
      {!longHair && (
        <g fill="#fffaf0" stroke="#e8dcc4" strokeWidth=".5">
          {[
            [68.5, 23.5],
            [71.3, 27],
            [72.4, 31.2],
            [71.6, 35.4],
          ].map(([cx, cy]) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.2" />
          ))}
        </g>
      )}

      {/* Gold earrings. */}
      <circle cx="39.5" cy="71" r="2.4" fill="#d2a54a" />
      <circle cx="80.5" cy="71" r="2.4" fill="#d2a54a" />
    </>
  );
}

function Man({
  skin,
  hair,
  shirt,
  sidePart,
  facialHair,
}: FaceProps & { shirt: string; sidePart: boolean; facialHair: (typeof facialHairStyles)[number] }) {
  const beard = facialHair === "beard";
  return (
    <>
      <path d={SHOULDERS} fill={shirt} />
      <path d={NECK} fill={skin} />
      <path d={NECK_SHADOW} fill="#000" fillOpacity=".1" />
      {/* Kurta collar and placket; a gold border on the cream, Kerala-style shirt. */}
      <path d="M47 94l13 13 13-13-3-2-10 9-10-9Z" fill="#000" fillOpacity=".12" />
      <path d="M60 107v43" stroke="#000" strokeOpacity=".14" strokeWidth="1.4" />
      {shirt === CREAM_SHIRT && (
        <path d="M13 139c14-2 29-3 47-3s33 1 47 3" stroke="#d2a54a" strokeWidth="2.4" fill="none" />
      )}

      <Face skin={skin} hair={hair} />
      {beard && (
        // Short beard along the jaw, leaving the cheeks clear.
        <path
          d="M40.5 63c0 15 8 24.5 19.5 24.5S79.5 78 79.5 63c-2 6-5 9-8 9.5-3-2.5-7-3.5-11.5-3.5s-8.5 1-11.5 3.5c-3-.5-6-3.5-8-9.5Z"
          fill={hair}
        />
      )}
      {facialHair !== "none" && (
        <path d="M51.5 73.5q4.5-3.4 8.5-1.2 4-2.2 8.5 1.2-4.2 2.4-8.5.6-4.3 1.8-8.5-.6Z" fill={hair} />
      )}
      <path
        d="M55 77.5q5 3.6 10 0"
        stroke={beard ? "#c98d6e" : "#6e3a2c"}
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
      />

      {sidePart ? (
        // Side-swept hair with short sideburns.
        <path
          d="M40 66c-3-6-4-13-3-20 2-13 11-21 23-21 13 0 22 8 23 20 1 7 0 14-3 21-1-7-2-12-5-16-5 2-12 1-17-3-4 4-11 6-16 6-1 4-2 8-2 13Z"
          fill={hair}
        />
      ) : (
        // Short crop.
        <path d="M39 61c-2-20 8-33 21-33s23 13 21 33c-2-6-4-10-7-12-8-2.5-20-2.5-28 0-3 2-5 6-7 12Z" fill={hair} />
      )}
    </>
  );
}
