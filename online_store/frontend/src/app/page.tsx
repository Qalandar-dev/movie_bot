import { SystemStatus } from "@/features/system/system-status";

/**
 * Phase 2 landing page: confirms the frontend ↔ API ↔ database/Redis chain works.
 * Replaced by the login screen and dashboard in Phase 7.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-4">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Online Store</h1>
        <p className="text-muted-foreground text-sm">Boshqaruv paneli</p>
      </div>
      <SystemStatus />
    </main>
  );
}
