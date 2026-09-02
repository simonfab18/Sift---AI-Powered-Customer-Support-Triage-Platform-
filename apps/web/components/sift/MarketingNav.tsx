import Link from "next/link";

import { SiftLogo } from "@/components/sift/SiftLogo";

const nav = [
  ["Features", "/features"],
  ["How It Works", "/how-it-works"],
  ["Pricing", "/pricing"],
  ["Resources", "/resources"],
  ["About", "/about"],
];

export function MarketingNav() {
  return (
    <header className="marketing-nav landing-nav">
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
            Login
          </Link>
          <Link className="button primary nav-cta" href="/signup">
            Start free
          </Link>
        </div>
      </div>
    </header>
  );
}



