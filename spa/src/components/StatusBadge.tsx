export function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="muted">—</span>;
  const cls =
    status === "APPROVED"
      ? "approved"
      : status === "REJECTED"
        ? "rejected"
        : status === "CHANGES_REQUESTED"
          ? "changes"
          : "pending";
  const label = status.replace(/_/g, " ").toLowerCase();
  return <span className={`badge ${cls}`}>{label}</span>;
}
