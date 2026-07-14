import Link from "next/link";

import { SiftLogo } from "@/components/sift/SiftLogo";

const nav = [
  ["Product", "/product"],
  ["Solutions", "/solutions"],
  ["Security", "/security"],
  ["Pricing", "/pricing"],
  ["Resources", "/resources"],
];

export function MarketingNav() {
  return (
    <header className="marketing-nav">
      <div className="sift-container nav-inner">
        <SiftLogo />
        <nav className="nav-links" aria-label="Main navigation">
          {nav.map(([label, href]) => (
            <Link key={href} href={href}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="nav-actions">
          <Link className="quiet-link" href="/login">
            Sign in
          </Link>
          <Link className="button secondary" href="/contact">
            Book a demo
          </Link>
          <Link className="button primary" href="/signup">
            Start free
          </Link>
        </div>
      </div>
    </header>
  );
}
