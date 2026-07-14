import Link from "next/link";

export function SiftMark({ dark = false }: { dark?: boolean }) {
  return (
    <span className={dark ? "sift-mark sift-mark-dark" : "sift-mark"} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

export function SiftLogo({ href = "/", dark = false }: { href?: string; dark?: boolean }) {
  return (
    <Link href={href} className="sift-logo" aria-label="Sift home">
      <SiftMark dark={dark} />
      <span>Sift</span>
    </Link>
  );
}
