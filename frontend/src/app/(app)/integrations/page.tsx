"use client";

import * as React from "react";
import {
  Camera,
  Check,
  CircleAlert,
  Database,
  Globe2,
  Plug,
  Settings2,
  Webhook,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getIntegrations } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import type { Integration } from "@/lib/types";

const CATEGORY_ICONS: Record<Integration["category"], React.ElementType> = {
  "Fleet cameras": Camera,
  "Dashcam providers": Camera,
  GIS: Globe2,
  "Asset management": Database,
  Developer: Webhook,
};

const CATEGORIES: Integration["category"][] = [
  "Fleet cameras",
  "Dashcam providers",
  "GIS",
  "Asset management",
  "Developer",
];

export default function IntegrationsPage() {
  const integrations = useAsync(() => getIntegrations(), []);
  const [configuring, setConfiguring] = React.useState<Integration | null>(null);

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <PageHeader
        title="Integrations"
        description="Connect capture sources, GIS, and asset-management systems. Only authorized, consented data sources can be enrolled."
      />

      {integrations.loading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : (
        CATEGORIES.map((category) => {
          const items = (integrations.data ?? []).filter(
            (i) => i.category === category,
          );
          if (items.length === 0) return null;
          const Icon = CATEGORY_ICONS[category];
          return (
            <section key={category} aria-label={category}>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                <Icon className="h-4 w-4" aria-hidden />
                {category}
              </h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {items.map((integration) => (
                  <Card key={integration.id} className="flex flex-col">
                    <CardHeader className="flex-row items-start justify-between space-y-0">
                      <CardTitle className="text-sm">{integration.name}</CardTitle>
                      {integration.status === "connected" ? (
                        <Badge variant="success">
                          <Check aria-hidden /> Connected
                        </Badge>
                      ) : integration.status === "attention" ? (
                        <Badge variant="warning">
                          <CircleAlert aria-hidden /> Attention
                        </Badge>
                      ) : (
                        <Badge variant="muted">
                          <Plug aria-hidden /> Available
                        </Badge>
                      )}
                    </CardHeader>
                    <CardContent className="flex flex-1 flex-col gap-3">
                      <p className="flex-1 text-sm text-muted-foreground">
                        {integration.description}
                      </p>
                      <p className="text-xs text-muted-foreground/80">{integration.detail}</p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="self-start"
                        onClick={() => setConfiguring(integration)}
                      >
                        <Settings2 aria-hidden />
                        {integration.status === "available" ? "Set up" : "Configure"}
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </section>
          );
        })
      )}

      <Sheet open={!!configuring} onOpenChange={(open) => !open && setConfiguring(null)}>
        <SheetContent className="overflow-y-auto">
          {configuring ? (
            <>
              <SheetHeader>
                <SheetTitle>{configuring.name}</SheetTitle>
                <SheetDescription>
                  Demo configuration — settings are not persisted and no external
                  service is contacted.
                </SheetDescription>
              </SheetHeader>
              <div className="space-y-5 p-5 pt-2">
                <div className="space-y-1.5">
                  <Label htmlFor="int-endpoint">Endpoint / portal URL</Label>
                  <Input
                    id="int-endpoint"
                    placeholder="https://example.gov/portal"
                    defaultValue={
                      configuring.status === "connected"
                        ? "https://gis.meridianfalls.example.gov"
                        : ""
                    }
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="int-key">API key</Label>
                  <Input id="int-key" type="password" placeholder="••••••••••••" />
                  <p className="text-xs text-muted-foreground">
                    Keys are scoped read-only by default and stored encrypted in
                    production deployments.
                  </p>
                </div>
                <div className="flex items-center justify-between rounded-md border p-3">
                  <div>
                    <Label htmlFor="int-sync" className="text-sm">
                      Hourly sync
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Push confirmed detections automatically
                    </p>
                  </div>
                  <Switch id="int-sync" defaultChecked={configuring.status === "connected"} />
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => {
                      toast.success("Configuration saved (demo)", {
                        description: "No external connection was made.",
                      });
                      setConfiguring(null);
                    }}
                  >
                    Save
                  </Button>
                  <Button variant="outline" onClick={() => setConfiguring(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
