import { Skeleton } from "@/features/dashboard/components/ui";

/** Shown while a dashboard page loads its data; mirrors the common page layout to avoid jumps. */
export default function DashboardLoading() {
  return (
    <div role="status" aria-label="Loading" className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-60" />
        <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      </div>
      <Skeleton className="h-44 rounded-xl" />
      <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-32 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    </div>
  );
}
