import type { ComponentProps } from "react";

type IconProps = ComponentProps<"svg">;

/** Decorative 24px stroke icons. Give the parent control an accessible label. */
function Icon({ children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.4-4.4" />
    </Icon>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 12h16M4 17h10" />
    </Icon>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Icon>
  );
}

export function UserIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8.5" r="3.5" />
      <path d="M5 19.5c1.2-3.2 3.8-5 7-5s5.8 1.8 7 5" />
    </Icon>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m14.5 6-6 6 6 6" />
    </Icon>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="m9.5 6 6 6-6 6" />
    </Icon>
  );
}

export function ShieldCheckIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3.5 5 6v5.5c0 4.3 2.9 7.6 7 9 4.1-1.4 7-4.7 7-9V6l-7-2.5Z" />
      <path d="m9 12 2.2 2.2L15.5 10" />
    </Icon>
  );
}

export function HeartUsersIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="8" cy="8" r="3" />
      <path d="M2.5 19c.6-3.3 2.7-5.2 5.5-5.2 1.4 0 2.6.5 3.5 1.3" />
      <path d="M17 20s-4.5-2.6-4.5-5.6c0-1.3 1-2.4 2.3-2.4.9 0 1.7.5 2.2 1.2.5-.7 1.3-1.2 2.2-1.2 1.3 0 2.3 1.1 2.3 2.4 0 3-4.5 5.6-4.5 5.6Z" />
    </Icon>
  );
}

export function LockIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
      <path d="M12 14.5v2.5" />
    </Icon>
  );
}

export function MessagesIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 5.5h11a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5H9l-3.5 3v-3H4A1.5 1.5 0 0 1 2.5 13V7A1.5 1.5 0 0 1 4 5.5Z" />
      <path d="M19.5 9h.5a1.5 1.5 0 0 1 1.5 1.5v6A1.5 1.5 0 0 1 20 18h-1v2.5L16 18h-4.5" />
    </Icon>
  );
}

export function UserPlusIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="10" cy="8" r="3.5" />
      <path d="M3.5 19.5c1.1-3.2 3.6-5 6.5-5 1.6 0 3 .5 4.2 1.4" />
      <path d="M18 13v6M15 16h6" />
    </Icon>
  );
}

export function SlidersIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
      <circle cx="15" cy="7" r="2" />
      <circle cx="9" cy="17" r="2" />
    </Icon>
  );
}

export function HeartIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 19.5s-7.5-4.4-7.5-9.6A4 4 0 0 1 12 7.6a4 4 0 0 1 7.5 2.3c0 5.2-7.5 9.6-7.5 9.6Z" />
    </Icon>
  );
}

export function UsersIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3 19.5c.9-3.1 3.2-4.9 6-4.9s5.1 1.8 6 4.9" />
      <path d="M15.5 5.6a3.2 3.2 0 0 1 0 5.8M17.5 14.9c1.6.6 2.8 2.2 3.5 4.6" />
    </Icon>
  );
}

export function CompassIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m15.5 8.5-2 5-5 2 2-5 5-2Z" />
    </Icon>
  );
}

export function MapPinIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" />
      <circle cx="12" cy="10" r="2.4" />
    </Icon>
  );
}

export function InstagramIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="3.5" width="17" height="17" rx="4.5" />
      <circle cx="12" cy="12" r="3.8" />
      <circle cx="17" cy="7" r=".9" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function FacebookIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M14.5 8H16V4.6c-.3 0-1.3-.1-2.4-.1-2.4 0-4 1.5-4 4.2V11H7v3.5h2.6V21H13v-6.5h2.6L16 11h-3V9.1c0-.7.3-1.1 1.5-1.1Z" />
    </Icon>
  );
}

export function YouTubeIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M21 8.2a2.6 2.6 0 0 0-1.8-1.9C17.6 6 12 6 12 6s-5.6 0-7.2.3A2.6 2.6 0 0 0 3 8.2 27 27 0 0 0 2.7 12c0 1.3.1 2.5.3 3.8a2.6 2.6 0 0 0 1.8 1.9C6.4 18 12 18 12 18s5.6 0 7.2-.3a2.6 2.6 0 0 0 1.8-1.9c.2-1.3.3-2.5.3-3.8s-.1-2.5-.3-3.8Z" />
      <path d="m10.2 14.6 4.4-2.6-4.4-2.6v5.2Z" fill="currentColor" />
    </Icon>
  );
}

export function WhatsAppIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M4 20.5 5.2 17A8.5 8.5 0 1 1 8 19.6l-4 .9Z" />
      <path d="M9.2 8.6c.2-.4.6-.5.9-.4l.6 1.4c.1.3 0 .5-.2.7l-.4.5c.5 1 1.3 1.8 2.3 2.3l.5-.4c.2-.2.4-.3.7-.2l1.4.6c.2.2.2.6-.1.9-.4.6-1.1.9-1.8.7a7.3 7.3 0 0 1-4.6-4.6c-.2-.7.1-1.4.7-1.5Z" />
    </Icon>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </Icon>
  );
}

export function VerifiedIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3l2.2 1.6 2.7-.1.9 2.6 2.2 1.6-.8 2.6.8 2.6-2.2 1.6-.9 2.6-2.7-.1L12 21l-2.2-1.6-2.7.1-.9-2.6-2.2-1.6.8-2.6-.8-2.6 2.2-1.6.9-2.6 2.7.1L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  );
}
