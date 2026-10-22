import { redirect } from "next/navigation";

/** /dashboard/interests has no page of its own; received interests are the usual starting point. */
export default function InterestsPage() {
  redirect("/dashboard/interests/received");
}
