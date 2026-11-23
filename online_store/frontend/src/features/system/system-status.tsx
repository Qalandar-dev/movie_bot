"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, RefreshCw, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { fetchReadiness } from "@/services/system";

function ServiceRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <li className="flex items-center justify-between py-2">
      <span className="text-sm">{label}</span>
      {ok ? (
        <Badge variant="success">
          <CheckCircle2 aria-hidden /> Ishlayapti
        </Badge>
      ) : (
        <Badge variant="destructive">
          <XCircle aria-hidden /> Ulanmagan
        </Badge>
      )}
    </li>
  );
}

export function SystemStatus() {
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: fetchReadiness,
    refetchInterval: 30_000,
  });

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>Tizim holati</CardTitle>
        <CardDescription>Backend xizmatlari bilan aloqa</CardDescription>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <p role="status" className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Tekshirilmoqda…
          </p>
        ) : error ? (
          <div role="alert" className="space-y-3">
            <p className="text-destructive text-sm">
              {error instanceof ApiError ? error.message : "Noma’lum xatolik yuz berdi."}
            </p>
            <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw aria-hidden /> Qayta urinish
            </Button>
          </div>
        ) : (
          <ul className="divide-y">
            <ServiceRow label="API" ok />
            <ServiceRow label="PostgreSQL" ok={data.database} />
            <ServiceRow label="Redis" ok={data.redis} />
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
