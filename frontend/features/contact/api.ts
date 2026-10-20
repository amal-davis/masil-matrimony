import { api } from "@/lib/api/client";

import type { ContactValues } from "./schema";

/** 201 body of POST /enquiries/. `id` is null only when the spam trap was triggered. */
export interface EnquiryCreated {
  id: string | null;
}

/** Store a contact-form message as an enquiry for staff to follow up. */
export function submitEnquiry(values: ContactValues) {
  return api.post<EnquiryCreated>("/enquiries/", values);
}
