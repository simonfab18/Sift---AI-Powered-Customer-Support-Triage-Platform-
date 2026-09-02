export function OrganizationEmptyState() {
  return (
    <div className="mt-8 rounded-lg border border-dashed border-slate-300 bg-white p-6">
      <h2 className="text-base font-semibold">No organization selected</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">
        Once authentication UI is connected, owners will create organizations here and manage
        admins and agents from the same organization-scoped workspace.
      </p>
    </div>
  );
}



