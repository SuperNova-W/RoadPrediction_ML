"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";
import { APP_NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const reduceMotion = useReducedMotion();

  return (
    <nav aria-label="Primary" className="flex-1 space-y-0.5 px-3">
      {APP_NAV.map((item) => {
        const active =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-white/60",
              active
                ? "text-white"
                : "text-navy-muted hover:bg-white/5 hover:text-navy-foreground",
            )}
          >
            {active ? (
              <motion.span
                layoutId={onNavigate ? undefined : "sidebar-active"}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 500, damping: 40 }
                }
                className="absolute inset-0 rounded-md bg-white/10 ring-1 ring-white/10"
                aria-hidden
              />
            ) : null}
            <item.icon className="relative h-4 w-4 shrink-0" aria-hidden />
            <span className="relative">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
