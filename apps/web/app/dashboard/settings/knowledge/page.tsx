import { KnowledgeSettings } from "@/features/settings/components/KnowledgeSettings";
import { SettingsNav } from "@/features/settings/components/SettingsNav";

export default function KnowledgeSettingsPage() {
  return (
    <section className="space-y-6">
      <SettingsNav />
      <KnowledgeSettings />
    </section>
  );
}



