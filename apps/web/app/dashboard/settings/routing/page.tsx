import { RoutingRulesSettings } from "@/features/settings/components/RoutingRulesSettings";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function RoutingSettingsPage() {
  return (
    <section className="space-y-6">
      <SettingsNav />
      <RoutingRulesSettings />
    </section>
  );
}
