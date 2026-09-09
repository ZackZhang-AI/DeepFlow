export function DemoBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 ${className}`}
    >
      演示样例
    </span>
  );
}
