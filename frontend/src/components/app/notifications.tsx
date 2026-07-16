"use client";

import * as React from "react";
import { Bell, CircleAlert, ClipboardList, ScanSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { getNotifications, markNotificationsRead } from "@/lib/api";
import type { AppNotification } from "@/lib/types";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const KIND_ICONS = {
  detection: ScanSearch,
  work_order: ClipboardList,
  system: CircleAlert,
} as const;

export function NotificationCenter() {
  const [items, setItems] = React.useState<AppNotification[]>([]);

  React.useEffect(() => {
    getNotifications().then(setItems).catch(() => {});
  }, []);

  const unread = items.filter((n) => !n.read).length;

  return (
    <Popover
      onOpenChange={(open) => {
        if (!open && unread > 0) {
          markNotificationsRead().then(() =>
            setItems((prev) => prev.map((n) => ({ ...n, read: true }))),
          );
        }
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
        >
          <Bell className="h-4 w-4" aria-hidden />
          {unread > 0 ? (
            <span
              className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-destructive ring-2 ring-card"
              aria-hidden
            />
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          {unread > 0 ? (
            <span className="text-xs text-muted-foreground">{unread} unread</span>
          ) : null}
        </div>
        <Separator />
        <ul className="max-h-80 overflow-y-auto py-1" aria-label="Notifications">
          {items.map((n) => {
            const Icon = KIND_ICONS[n.kind];
            return (
              <li
                key={n.id}
                className={cn(
                  "flex gap-3 px-4 py-2.5 text-sm",
                  !n.read && "bg-accent/60",
                )}
              >
                <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0">
                  <p className="font-medium leading-snug">{n.title}</p>
                  <p className="text-xs text-muted-foreground">{n.body}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground/80">
                    {formatRelative(n.timestamp)}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
