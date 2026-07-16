"use client";

import * as React from "react";
import Link from "next/link";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "framer-motion";
import {
  ArrowRight,
  Camera,
  CheckCircle2,
  ClipboardList,
  FileDown,
  Hammer,
  History,
  ListOrdered,
  Lock,
  ScanSearch,
  Scale,
  ServerCog,
  UserCheck,
  Users,
} from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BRAND } from "@/lib/brand";
import { HeroDemo } from "./hero-demo";
import { RequestDemoDialog } from "./request-demo";
import { ShowcaseTabs } from "./showcase";

/* ------------------------------------------------------------------ */
/* Shared reveal helper                                                */
/* ------------------------------------------------------------------ */

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                                */
/* ------------------------------------------------------------------ */

export function Hero() {
  const reduceMotion = useReducedMotion();
  const ref = React.useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });
  const parallax = useTransform(scrollYProgress, [0, 1], [0, reduceMotion ? 0 : 60]);

  return (
    <section
      ref={ref}
      className="relative overflow-hidden bg-navy text-navy-foreground"
      id="product"
    >
      <div className="bg-blueprint-grid-dark absolute inset-0" aria-hidden />
      <div
        className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent"
        aria-hidden
      />
      {/* Glow */}
      <div
        className="pointer-events-none absolute left-1/2 top-[-240px] h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-primary/25 blur-[140px]"
        aria-hidden
      />

      <div className="container relative grid gap-12 py-20 lg:grid-cols-2 lg:items-center lg:py-28">
        <div>
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            <Badge
              variant="outline"
              className="border-white/20 bg-white/5 text-navy-foreground"
            >
              Built for municipal public works
            </Badge>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.08] tracking-tight text-white sm:text-5xl xl:text-6xl">
              Turn road imagery into prioritized maintenance decisions
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-navy-muted">
              {BRAND.name} analyzes street-level images from your municipal
              vehicles and authorized fleet cameras, flags likely damage for
              human review, and turns confirmed issues into a ranked repair
              plan — on a map your whole department can work from.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <RequestDemoDialog>
                <Button size="lg">Request a demo</Button>
              </RequestDemoDialog>
              <Button size="lg" variant="outline" className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white" asChild>
                <Link href="/dashboard">
                  Explore the platform <ArrowRight aria-hidden />
                </Link>
              </Button>
            </div>
            <p className="mt-6 text-sm text-navy-muted/80">
              AI detections are always reviewed by your team before work is
              scheduled. No satellite feeds, no unauthorized cameras — only
              imagery you own or license.
            </p>
          </motion.div>
        </div>

        <motion.div style={{ y: parallax }}>
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 28, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          >
            <HeroDemo />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Workflow                                                            */
/* ------------------------------------------------------------------ */

const STAGES = [
  {
    icon: Camera,
    title: "Capture",
    body: "Municipal vehicles and enrolled fleets record road-facing imagery on their normal routes.",
  },
  {
    icon: ScanSearch,
    title: "Detect",
    body: "Computer vision flags cracks and potholes with bounding boxes, class, and confidence.",
  },
  {
    icon: UserCheck,
    title: "Review",
    body: "Inspectors confirm or reject each detection — every decision is audit-logged.",
  },
  {
    icon: ListOrdered,
    title: "Prioritize",
    body: "Confirmed issues get a repair-priority score from severity, road importance, and age.",
  },
  {
    icon: Hammer,
    title: "Repair",
    body: "Work orders route to crews or contractors, with completion tracked against the map.",
  },
];

export function Workflow() {
  const reduceMotion = useReducedMotion();
  return (
    <section id="how-it-works" className="border-b bg-background py-20 lg:py-28">
      <div className="container">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">
            How it works
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            One connected loop, from windshield to work order
          </h2>
        </Reveal>

        <div className="relative mt-14">
          {/* Connecting line */}
          <div className="absolute left-6 top-0 h-full w-px bg-border lg:left-0 lg:top-6 lg:h-px lg:w-full" aria-hidden>
            <motion.div
              className="h-full w-full origin-top bg-primary lg:origin-left"
              initial={reduceMotion ? { scaleY: 1, scaleX: 1 } : { scaleY: 0, scaleX: 0 }}
              whileInView={{ scaleY: 1, scaleX: 1 }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 1.4, ease: "easeInOut" }}
            />
          </div>

          <ol className="grid gap-10 lg:grid-cols-5 lg:gap-6">
            {STAGES.map((stage, i) => (
              <Reveal key={stage.title} delay={i * 0.12}>
                <li className="relative flex gap-5 pl-16 lg:flex-col lg:gap-4 lg:pl-0 lg:pt-16">
                  <span
                    className="absolute left-0 top-0 flex h-12 w-12 items-center justify-center rounded-full border-2 border-primary bg-card text-primary shadow-card lg:left-0"
                    aria-hidden
                  >
                    <stage.icon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Step {i + 1}
                    </p>
                    <h3 className="mt-1 text-lg font-semibold">{stage.title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                      {stage.body}
                    </p>
                  </div>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Product showcase                                                    */
/* ------------------------------------------------------------------ */

export function Showcase() {
  return (
    <section className="border-b bg-muted/40 py-20 lg:py-28">
      <div className="container">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">
            The platform
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            An operations console, not another dashboard
          </h2>
          <p className="mt-4 text-muted-foreground">
            Map-first triage, honest review workflows, and reporting your
            council can act on.
          </p>
        </Reveal>
        <Reveal delay={0.15} className="mt-10">
          <ShowcaseTabs />
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Government section                                                  */
/* ------------------------------------------------------------------ */

const GOV_FEATURES = [
  {
    icon: UserCheck,
    title: "Human review, always",
    body: "No detection becomes a work order without a person confirming it. Reviewer identity and timing are recorded.",
  },
  {
    icon: History,
    title: "Complete audit history",
    body: "Every confirmation, rejection, threshold change, and export is logged and reviewable by administrators.",
  },
  {
    icon: Users,
    title: "Role-based access",
    body: "Admins, supervisors, engineers, inspectors, and read-only viewers — each sees exactly what their role needs.",
  },
  {
    icon: FileDown,
    title: "Exportable reporting",
    body: "CSV and GIS-friendly exports for council packets, budget requests, and your existing asset-management systems.",
  },
  {
    icon: ServerCog,
    title: "Deployment flexibility",
    body: "Cloud-hosted or deployed in your government cloud tenancy, with data residency options and SSO integration.",
  },
  {
    icon: Lock,
    title: "Data you control",
    body: "Imagery comes only from vehicles you own or fleets with signed agreements. You decide retention and sharing.",
  },
];

export function Government() {
  return (
    <section id="government" className="border-b bg-navy py-20 text-navy-foreground lg:py-28">
      <div className="bg-blueprint-grid-dark absolute inset-0" aria-hidden />
      <div className="container relative">
        <Reveal className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-widest text-[#8ab4ff]">
            Built for government
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Procurement-ready by design
          </h2>
          <p className="mt-4 text-navy-muted">
            {BRAND.name} is built around the controls public agencies actually
            need — review trails, access controls, and honest reporting.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" id="security">
          {GOV_FEATURES.map((feature, i) => (
            <Reveal key={feature.title} delay={i * 0.08}>
              <div className="h-full rounded-lg border border-white/10 bg-white/5 p-5 transition-colors hover:bg-white/[0.08]">
                <feature.icon className="h-5 w-5 text-[#8ab4ff]" aria-hidden />
                <h3 className="mt-3 font-semibold text-white">{feature.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-navy-muted">
                  {feature.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Trust / limitations                                                 */
/* ------------------------------------------------------------------ */

const LIMITS = [
  {
    icon: UserCheck,
    title: "AI needs human judgment",
    body: "Detections are proposals, not verdicts. Shadows, sealed cracks, and utility cuts can fool a model — your inspectors make the call.",
  },
  {
    icon: Scale,
    title: "Severity is an estimate",
    body: "Severity and priority scores are planning heuristics derived from image evidence. They order the queue; they don't certify a road's condition.",
  },
  {
    icon: ClipboardList,
    title: "Not an engineering assessment",
    body: "RoadLens does not replace licensed engineering inspections, PCI surveys, or structural evaluations required by your standards.",
  },
];

export function Trust() {
  return (
    <section className="border-b bg-background py-20 lg:py-24">
      <div className="container">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-primary">
            What RoadLens is — and isn&apos;t
          </p>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
            Honest about the limits
          </h2>
        </Reveal>
        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {LIMITS.map((limit, i) => (
            <Reveal key={limit.title} delay={i * 0.1}>
              <div className="h-full rounded-lg border bg-card p-6 shadow-card">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-warning/10">
                  <limit.icon className="h-5 w-5 text-warning" aria-hidden />
                </span>
                <h3 className="mt-4 font-semibold">{limit.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {limit.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* CTA + footer                                                        */
/* ------------------------------------------------------------------ */

export function FinalCta() {
  return (
    <section className="bg-background py-20 lg:py-24">
      <div className="container">
        <Reveal>
          <div className="relative overflow-hidden rounded-2xl bg-navy px-8 py-14 text-center text-white sm:px-14">
            <div className="bg-blueprint-grid-dark absolute inset-0" aria-hidden />
            <div
              className="pointer-events-none absolute left-1/2 top-full h-64 w-[560px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/30 blur-[100px]"
              aria-hidden
            />
            <div className="relative">
              <h2 className="mx-auto max-w-xl text-3xl font-semibold tracking-tight sm:text-4xl">
                See your road network the way your crews do
              </h2>
              <p className="mx-auto mt-4 max-w-lg text-navy-muted">
                A 30-minute walkthrough with imagery from a comparable
                municipality. No procurement commitment required.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <RequestDemoDialog>
                  <Button size="lg">Request a demo</Button>
                </RequestDemoDialog>
                <Button
                  size="lg"
                  variant="outline"
                  className="border-white/25 bg-transparent text-white hover:bg-white/10 hover:text-white"
                  asChild
                >
                  <Link href="/dashboard">Explore the demo workspace</Link>
                </Button>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t bg-navy text-navy-muted">
      <div className="container grid gap-10 py-14 md:grid-cols-4">
        <div className="md:col-span-2">
          <Logo dark />
          <p className="mt-3 max-w-sm text-sm leading-relaxed">
            {BRAND.description}
          </p>
          <p className="mt-4 text-xs text-navy-muted/70">
            This site is a product prototype. All municipalities, people, and
            statistics shown are fictional demo data.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold text-white">Product</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><a href="#product" className="hover:text-white">Overview</a></li>
            <li><a href="#how-it-works" className="hover:text-white">How it works</a></li>
            <li><a href="#government" className="hover:text-white">Government</a></li>
            <li><a href="#security" className="hover:text-white">Security</a></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold text-white">Platform</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link href="/dashboard" className="hover:text-white">Demo workspace</Link></li>
            <li><Link href="/map" className="hover:text-white">Operational map</Link></li>
            <li><Link href="/analytics" className="hover:text-white">Analytics</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="container flex flex-col items-center justify-between gap-2 py-5 text-xs sm:flex-row">
          <p>© 2026 {BRAND.legalName} (fictional). Prototype for demonstration.</p>
          <p className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-success" aria-hidden />
            AI detections always require human review.
          </p>
        </div>
      </div>
    </footer>
  );
}
