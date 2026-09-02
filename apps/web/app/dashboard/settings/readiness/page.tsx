import { ReleaseReadinessSettings } from "@/features/settings/components/ReleaseReadinessSettings";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function ReadinessSettingsPage() {
  return (
    <section className="space-y-6">
      <SettingsNav />
      <ReleaseReadinessSettings />
    </section>
  );
}


