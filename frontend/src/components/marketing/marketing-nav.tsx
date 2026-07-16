"use client";

import * as React from "react";
import Link from "next/link";
import { Menu } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { MARKETING_NAV } from "@/lib/nav";
import { RequestDemoDialog } from "./request-demo";

export function MarketingNav() {
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-navy backdrop-blur supports-[backdrop-filter]:bg-navy/90">
      <div className="container flex h-16 items-center gap-6">
        <Link
          href="/"
          className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          aria-label="RoadLens home"
        >
          <Logo dark />
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Marketing">
          {MARKETING_NAV.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm text-navy-muted transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="ml-auto hidden items-center gap-2 md:flex">
          <Button variant="ghost" className="text-navy-foreground hover:bg-white/10 hover:text-white" asChild>
            <Link href="/dashboard">Sign in</Link>
          </Button>
          <RequestDemoDialog>
            <Button>Request a demo</Button>
          </RequestDemoDialog>
        </div>

        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="ml-auto text-navy-foreground hover:bg-white/10 md:hidden"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" aria-hidden />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="border-navy-border bg-navy text-navy-foreground [&>button]:text-navy-foreground">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <nav className="mt-8 flex flex-col gap-1 px-2" aria-label="Mobile">
              {MARKETING_NAV.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className="rounded-md px-3 py-2.5 text-base text-navy-foreground hover:bg-white/10"
                >
                  {item.label}
                </a>
              ))}
              <Link
                href="/dashboard"
                className="rounded-md px-3 py-2.5 text-base text-navy-foreground hover:bg-white/10"
              >
                Sign in
              </Link>
              <div className="px-3 pt-3">
                <RequestDemoDialog>
                  <Button className="w-full">Request a demo</Button>
                </RequestDemoDialog>
              </div>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
