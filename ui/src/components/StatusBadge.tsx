import type { AppStatus } from "../types";
import { STATUS_LABEL } from "../types";

const styles: Record<AppStatus, string> = {
  draft: "bg-canvas text-muted",
  applied: "bg-blue-50 text-primary",
  interview: "bg-violet-50 text-secondary",
  offer: "bg-green-50 text-success",
  rejected: "bg-red-50 text-danger",
};

export function StatusBadge({ status }: { status: AppStatus }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}>
      {STATUS_LABEL[status]}
    </span>
  );
}
