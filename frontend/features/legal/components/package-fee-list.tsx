import { Suspense } from "react";

import { getPackages } from "@/features/packages/api";

import { packagePriceSummary, packageTitle } from "../package-summary";
import { A, List, P } from "./legal-document";

async function PackageFees() {
  const result = await getPackages();
  if (!result.ok || result.packages.length === 0) {
    return (
      <P>
        The current packages and fees couldn&apos;t be loaded just now. They are listed on our{" "}
        <A href="/our-packages">Membership page</A>.
      </P>
    );
  }
  return (
    <List
      items={result.packages.map((pkg) => (
        <>
          <strong className="font-semibold">{packageTitle(pkg)}</strong>: {packagePriceSummary(pkg)}
        </>
      ))}
    />
  );
}

/** The current packages and fees, from the same API as /our-packages. Reads the API at request time. */
export function PackageFeeList() {
  return (
    <Suspense fallback={<P>Loading the current packages…</P>}>
      <PackageFees />
    </Suspense>
  );
}
