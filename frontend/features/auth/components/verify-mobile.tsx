"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { parsePhoneNumberFromString, type CountryCode } from "libphonenumber-js";
import Link from "next/link";
import { useId, useState, useTransition } from "react";
import { useForm, useWatch } from "react-hook-form";

import { resendRegistrationCode, verifyRegistrationCode, type PendingCode } from "../actions";
import { LOGIN_PATH, REGISTER_PATH } from "../constants";
import {
  changeMobileSchema,
  DEFAULT_SMS_COUNTRY,
  SMS_COUNTRIES,
  type ChangeMobileInput,
  type ChangeMobileValues,
} from "../schema";
import { NoticeBox, primaryButton, Spinner, textLink, type Notice } from "./auth-ui";
import { MobileNumberInput } from "./mobile-number-input";
import { OtpStep, textButton } from "./otp-step";

const secondaryButton =
  "inline-flex h-13 w-full items-center justify-center rounded-md border-[1.5px] border-wine-600 bg-white px-8 text-base font-medium text-wine-600 transition-colors duration-200 hover:bg-brand-50 focus-visible:outline-wine-600 disabled:opacity-60";

/** The pending number split back into the picker's country and the national number, to prefill "Change". */
function splitNumber(e164: string): ChangeMobileInput {
  const parsed = parsePhoneNumberFromString(e164);
  const country = parsed?.country && SMS_COUNTRIES.includes(parsed.country) ? parsed.country : DEFAULT_SMS_COUNTRY;
  return { country, phone: parsed ? parsed.formatNational() : "" };
}

function StartAgain({ message }: { message: string }) {
  return (
    <div className="flex flex-col gap-5">
      <NoticeBox notice={{ kind: "error", message }} />
      <Link href={REGISTER_PATH} className={primaryButton}>
        Go to the registration form
      </Link>
      <p className="text-[0.9375rem] text-ink-muted">
        Already registered?{" "}
        <Link href={LOGIN_PATH} className={textLink}>
          Log in
        </Link>
      </p>
    </div>
  );
}

/** Correct the mobile number of a registration in progress; the other details are kept. */
function ChangeNumberForm({
  current,
  onSent,
  onCancel,
  onExpired,
}: {
  current: string;
  onSent: (pending: PendingCode) => void;
  onCancel: () => void;
  onExpired: (message: string) => void;
}) {
  const id = useId();
  const [notice, setNotice] = useState<Notice>(null);
  const [phoneRegistered, setPhoneRegistered] = useState(false);
  const [sending, startSending] = useTransition();
  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    setValue,
    getValues,
    control,
    formState: { errors },
  } = useForm<ChangeMobileInput, unknown, ChangeMobileValues>({
    resolver: zodResolver(changeMobileSchema),
    mode: "onTouched",
    defaultValues: splitNumber(current),
  });
  const country = useWatch({ control, name: "country" }) as CountryCode;

  const onSubmit = () =>
    startSending(async () => {
      setNotice(null);
      setPhoneRegistered(false);
      const result = await resendRegistrationCode(getValues());
      if (result.ok) {
        onSent(result.pending);
        return;
      }
      if (result.expired) {
        onExpired(result.message);
      } else if (result.field === "phone") {
        setPhoneRegistered(Boolean(result.phoneRegistered));
        setError("phone", { type: "server", message: result.message });
        setFocus("phone");
      } else {
        setNotice({ kind: "error", message: result.message });
      }
    });

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} aria-busy={sending} className="flex flex-col gap-5">
      <MobileNumberInput
        id={`${id}-phone`}
        label="Correct mobile number"
        tall
        country={country}
        onCountryChange={(code) => setValue("country", code, { shouldValidate: Boolean(errors.phone) })}
        error={errors.phone?.message}
        hint="Your other registration details are kept."
        inputProps={{ required: true, autoFocus: true, ...register("phone") }}
      />
      {phoneRegistered && (
        <p className="-mt-3 text-[0.9375rem]">
          <Link href={LOGIN_PATH} className={textLink}>
            Log in with this number instead
          </Link>
        </p>
      )}
      <NoticeBox notice={notice} />
      <button type="submit" disabled={sending} className={primaryButton}>
        {sending && <Spinner />}
        {sending ? "Sending code…" : "Send code to this number"}
      </button>
      <button type="button" onClick={onCancel} disabled={sending} className={secondaryButton}>
        Cancel
      </button>
    </form>
  );
}

/**
 * Registration step 2: the code sent to the new member's mobile. The account
 * is created only when the code is correct; the Server Action then signs the
 * member in and opens their profile.
 */
export function VerifyMobile({ initialPending }: { initialPending?: PendingCode }) {
  const [pending, setPending] = useState<PendingCode | undefined>(initialPending);
  const [changing, setChanging] = useState(false);
  const [ended, setEnded] = useState<string>();
  const [notice, setNotice] = useState<Notice>(null);

  if (ended) return <StartAgain message={ended} />;
  if (!pending) {
    return (
      <StartAgain message="There's no registration waiting for a code on this device, or it has expired. Please fill in the registration form." />
    );
  }

  if (changing) {
    return (
      <ChangeNumberForm
        current={pending.phoneNumber}
        onSent={(next) => {
          setPending(next);
          setChanging(false);
          setNotice({ kind: "info", message: `We've sent a code to ${next.maskedPhone}. The code sent to the old number no longer works.` });
        }}
        onCancel={() => setChanging(false)}
        onExpired={setEnded}
      />
    );
  }

  return (
    <OtpStep
      pending={pending}
      onPendingChange={setPending}
      verify={verifyRegistrationCode}
      resend={() => resendRegistrationCode()}
      onExpired={setEnded}
      submitLabel="Verify & create account"
      initialNotice={notice}
      changeNumber={
        <button type="button" onClick={() => setChanging(true)} className={textButton}>
          Change mobile number
        </button>
      }
    />
  );
}
