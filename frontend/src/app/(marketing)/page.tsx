import type { Metadata } from "next";
import { MarketingNav } from "@/components/marketing/marketing-nav";
import {
  FinalCta,
  Footer,
  Government,
  Hero,
  Showcase,
  Trust,
  Workflow,
} from "@/components/marketing/sections";
import { BRAND } from "@/lib/brand";

export const metadata: Metadata = {
  title: `${BRAND.name} — ${BRAND.tagline}`,
};

export default function MarketingPage() {
  return (
    <>
      <MarketingNav />
      <main>
        <Hero />
        <Workflow />
        <Showcase />
        <Government />
        <Trust />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
