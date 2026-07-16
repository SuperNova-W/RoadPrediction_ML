"use client";

import * as React from "react";
import Link from "next/link";
import { LogOut, Menu, Search, ShieldCheck, UserRound } from "lucide-react";
import { toast } from "sonner";
import { Logo } from "@/components/brand/logo";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Kbd } from "@/components/ui/kbd";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { CommandPaletteProvider, useCommandPalette } from "./command-palette";
import { MunicipalitySwitcher } from "./municipality-switcher";
import { NotificationCenter } from "./notifications";
import { SidebarNav } from "./sidebar-nav";

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col bg-navy text-navy-foreground">
      <div className="flex h-14 items-center px-5">
        <Link
          href="/"
          className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-white/60"
          aria-label="RoadLens home"
        >
          <Logo dark />
        </Link>
      </div>
      <div className="px-3 pb-4">
        <MunicipalitySwitcher dark />
      </div>
      <SidebarNav onNavigate={onNavigate} />
      <div className="mt-auto space-y-2 border-t border-navy-border p-4">
        <p className="flex items-center gap-2 text-xs text-navy-muted">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
          Demo workspace · mock data
        </p>
        <p className="text-[11px] leading-relaxed text-navy-muted/80">
          AI detections require human review and do not replace a licensed
          engineering assessment.
        </p>
      </div>
    </div>
  );
}

function SearchButton() {
  const { setOpen } = useCommandPalette();
  return (
    <Button
      variant="outline"
      className="h-9 w-full max-w-xs justify-start gap-2 text-muted-foreground sm:w-64"
      onClick={() => setOpen(true)}
      aria-label="Open global search (Command K)"
    >
      <Search className="h-4 w-4" aria-hidden />
      <span className="flex-1 truncate text-left text-sm">Search…</span>
      <Kbd aria-hidden>⌘K</Kbd>
    </Button>
  );
}

function UserMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label="User menu">
          <Avatar>
            <AvatarFallback>MO</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <p className="text-sm font-medium">Maya Okafor</p>
          <p className="text-xs font-normal text-muted-foreground">
            Public Works Director · Admin
          </p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings">
            <UserRound aria-hidden /> Profile &amp; settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => toast.info("Sign-out is demo-only", { description: "This prototype has no authentication backend." })}
        >
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <CommandPaletteProvider>
      <div className="flex min-h-dvh">
        {/* Desktop sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 lg:block" aria-label="Sidebar">
          <SidebarBody />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
          <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/75 sm:px-6">
            {/* Mobile nav */}
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                  <Menu className="h-5 w-5" aria-hidden />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72 border-navy-border bg-navy p-0 text-navy-foreground [&>button]:text-navy-foreground">
                <SheetTitle className="sr-only">Navigation</SheetTitle>
                <SidebarBody onNavigate={() => setMobileOpen(false)} />
              </SheetContent>
            </Sheet>

            <SearchButton />
            <div className="ml-auto flex items-center gap-1.5">
              <NotificationCenter />
              <UserMenu />
            </div>
          </header>

          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </CommandPaletteProvider>
  );
}
