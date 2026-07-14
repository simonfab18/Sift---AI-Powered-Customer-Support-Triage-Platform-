import { SiftAppShell } from "@/components/sift/SiftAppShell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <SiftAppShell>{children}</SiftAppShell>;
}
