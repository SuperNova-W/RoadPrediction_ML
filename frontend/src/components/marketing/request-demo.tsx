"use client";

import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function RequestDemoDialog({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setTimeout(() => {
      setBusy(false);
      setOpen(false);
      toast.success("Demo request noted (prototype)", {
        description:
          "This is a frontend prototype — nothing was sent. In production this reaches our government team.",
      });
    }, 600);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request a demo</DialogTitle>
          <DialogDescription>
            Tell us about your road network and we&apos;ll tailor a walkthrough.
            This prototype does not transmit your details anywhere.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="demo-name">Name</Label>
              <Input id="demo-name" required placeholder="Jordan Ellis" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="demo-email">Work email</Label>
              <Input
                id="demo-email"
                type="email"
                required
                placeholder="j.ellis@city.example.gov"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="demo-muni">Municipality / agency</Label>
            <Input id="demo-muni" required placeholder="City of …" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="demo-notes">What are you hoping to improve?</Label>
            <Textarea
              id="demo-notes"
              placeholder="e.g. pothole response times, PCI survey costs…"
            />
          </div>
          <DialogFooter className="pt-1">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Sending…" : "Request demo"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
