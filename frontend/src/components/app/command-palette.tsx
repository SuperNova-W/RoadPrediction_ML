"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ClipboardPlus, FileDown, MapPin } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { APP_NAV } from "@/lib/nav";
import { getIssues } from "@/lib/api";
import type { RoadIssue } from "@/lib/types";
import { DAMAGE_CLASSES } from "@/lib/types";

interface CommandPaletteContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const CommandPaletteContext = React.createContext<CommandPaletteContextValue>({
  open: false,
  setOpen: () => {},
});

export const useCommandPalette = () => React.useContext(CommandPaletteContext);

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const [issues, setIssues] = React.useState<RoadIssue[]>([]);
  const router = useRouter();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  React.useEffect(() => {
    if (open && issues.length === 0) {
      getIssues().then(setIssues).catch(() => {});
    }
  }, [open, issues.length]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <CommandPaletteContext.Provider value={{ open, setOpen }}>
      {children}
      <CommandDialog open={open} onOpenChange={setOpen} title="Global search">
        <CommandInput placeholder="Search issues, pages, actions…" />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Navigate">
            {APP_NAV.map((item) => (
              <CommandItem key={item.href} onSelect={() => go(item.href)}>
                <item.icon aria-hidden />
                {item.label}
                <span className="ml-2 truncate text-xs text-muted-foreground">
                  {item.description}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Actions">
            <CommandItem
              onSelect={() => {
                setOpen(false);
                router.push("/work-orders?new=1");
              }}
            >
              <ClipboardPlus aria-hidden />
              Create work order
            </CommandItem>
            <CommandItem
              onSelect={() => {
                setOpen(false);
                toast.info("Exports live on the Reports page", {
                  description: "CSV export is available; PDF is demo-only.",
                });
                router.push("/reports");
              }}
            >
              <FileDown aria-hidden />
              Export report
            </CommandItem>
          </CommandGroup>
          {issues.length > 0 ? (
            <>
              <CommandSeparator />
              <CommandGroup heading="Issues">
                {issues.slice(0, 8).map((issue) => (
                  <CommandItem
                    key={issue.id}
                    value={`${issue.id} ${issue.roadName} ${issue.classCode}`}
                    onSelect={() => go(`/issues/${issue.id}`)}
                  >
                    <MapPin aria-hidden />
                    <span className="tnum font-medium">{issue.id}</span>
                    <span className="truncate text-muted-foreground">
                      {issue.roadName} · {DAMAGE_CLASSES[issue.classCode].short}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          ) : null}
        </CommandList>
      </CommandDialog>
    </CommandPaletteContext.Provider>
  );
}
