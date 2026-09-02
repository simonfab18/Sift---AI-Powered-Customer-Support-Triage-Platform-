import { AuditLogSettings } from "@/features/settings/components/AuditLogSettings";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function AuditSettingsPage() {
  return (
    <section className="space-y-6">
      <SettingsNav />
      <AuditLogSettings />
    </section>
  );
}



