"use client";

import { Building2, Check, ChevronsUpDown } from "lucide-react";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DEMO_MUNICIPALITY, OTHER_MUNICIPALITIES } from "@/lib/brand";
import { cn } from "@/lib/utils";

export function MunicipalitySwitcher({ dark = false }: { dark?: boolean }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-sm outline-none transition-colors focus-visible:ring-2",
          dark
            ? "border-navy-border bg-white/5 text-navy-foreground hover:bg-white/10 focus-visible:ring-white/60"
            : "border-input bg-card hover:bg-muted focus-visible:ring-ring",
        )}
        aria-label="Switch municipality"
      >
        <Building2 className="h-4 w-4 shrink-0 opacity-70" aria-hidden />
        <span className="flex-1 truncate">
          <span className="block truncate font-medium leading-tight">
            {DEMO_MUNICIPALITY.name}
          </span>
          <span className={cn("block text-xs leading-tight", dark ? "text-navy-muted" : "text-muted-foreground")}>
            {DEMO_MUNICIPALITY.state} · Demo workspace
          </span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-60" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>Municipalities</DropdownMenuLabel>
        <DropdownMenuItem className="justify-between">
          {DEMO_MUNICIPALITY.name}, {DEMO_MUNICIPALITY.state}
          <Check className="h-4 w-4" aria-hidden />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {OTHER_MUNICIPALITIES.map((m) => (
          <DropdownMenuItem
            key={m.id}
            className="flex-col items-start gap-0"
            onSelect={() =>
              toast.info(`${m.name} is not provisioned in this demo`, {
                description: "Only the Meridian Falls demo workspace has data.",
              })
            }
          >
            <span>
              {m.name}, {m.state}
            </span>
            <span className="text-xs text-muted-foreground">Not provisioned in demo</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
