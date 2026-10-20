/**
 * Copies a flag SVG (country-flag-icons, MIT) into public/flags/ for every
 * country the contact form's phone picker lists. Re-run with `npm run flags`
 * after updating libphonenumber-js or country-flag-icons.
 */
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

import { getCountries } from "libphonenumber-js";

const require = createRequire(import.meta.url);
const source = join(dirname(require.resolve("country-flag-icons/package.json")), "3x2");
const target = new URL("../public/flags/", import.meta.url);

mkdirSync(target, { recursive: true });
copyFileSync(join(source, "..", "LICENSE"), new URL("LICENSE.txt", target));
for (const code of getCountries()) {
  copyFileSync(join(source, `${code}.svg`), new URL(`${code}.svg`, target));
}
console.log(`Copied ${getCountries().length} flags to public/flags/.`);
