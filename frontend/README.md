# RoadLens — frontend prototype

A production-quality frontend prototype for **RoadLens**, a B2G SaaS platform
that helps local governments detect, review, and prioritize road damage from
ground-level fleet imagery.

> **Prototype notice** — everything here runs on clearly fictional mock data
> (the "City of Meridian Falls"). No live model, backend, or municipal data is
> involved. The ingestion pipeline is simulated in the browser and labeled as
> such throughout the UI.

## Run it

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Checks:

```bash
npm run typecheck  # tsc --noEmit
npm run lint       # eslint (next/core-web-vitals + typescript)
npm run build      # production build
```

## Stack

Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS ·
Radix primitives (shadcn-style components) · Framer Motion · Recharts ·
MapLibre GL · Lucide icons · sonner.

Maps use two free, no-API-key basemaps: **CARTO retina raster tiles**
(OpenStreetMap data, crisp modern streets view) and **Esri World Imagery**
(real satellite/aerial view). The full-screen map has a Streets/Satellite
switch; issue-detail location maps default to satellite. Both carry their
required attribution.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Marketing site (hero scan animation, workflow, showcase, government/trust sections) |
| `/dashboard` | KPIs, city map, damage distribution, trends, recent detections, fleet status |
| `/executive` | Leadership brief: condition grade, budget vs. backlog, response times, district scorecard |
| `/network` | Street-segment condition grades, distribution chart, filters, trends |
| `/citizen-reports` | 311/portal intake matched to AI detections to avoid duplicate dispatches |
| `/issues` | Filterable/searchable issue table with map view, bulk actions, row expansion |
| `/issues/[id]` | Source image + animated bounding boxes, AI vs. human review, actions, timeline |
| `/ingestion` | Drag-and-drop upload with simulated Uploading → … → Ready pipeline, fleet cards |
| `/map` | Full-screen operational map: clustering, heatmap, layer toggles, time slider, drawer |
| `/work-orders` | Kanban board + table, crew assignment, status moves, linked detections |
| `/reports` | District comparison, class trends, priority distribution, completion rate, CSV export |
| `/integrations` | Camera/GIS/AMS integration cards with configuration drawers |
| `/settings` | Municipality profile, team & roles, thresholds, priority weights, audit log |

## Structure

```
src/
├── app/
│   ├── (marketing)/page.tsx      # landing page
│   ├── (app)/                    # authenticated app (shared AppShell layout)
│   │   ├── dashboard/ executive/ issues/ map/ network/
│   │   ├── citizen-reports/ ingestion/ work-orders/
│   │   ├── reports/ integrations/ settings/
│   │   ├── layout.tsx  loading.tsx  error.tsx
│   └── layout.tsx  globals.css   # root layout, design tokens (CSS vars)
├── components/
│   ├── ui/          # shadcn-style primitives (button, dialog, table, command…)
│   ├── app/         # shell: sidebar, topbar, command palette (⌘K), notifications
│   ├── marketing/   # hero demo animation, sections, showcase
│   ├── charts/      # Recharts wrappers with a validated, CVD-safe palette
│   ├── map/         # IssueMap — the replaceable MapLibre data layer
│   ├── domain/      # badges, procedural road image, bounding-box overlay
│   └── brand/       # logo
└── lib/
    ├── brand.ts     # product name/metadata — change branding here
    ├── tokens.ts    # chart/status hex tokens (validated palette)
    ├── nav.ts       # central navigation config
    ├── types.ts     # typed domain models
    ├── api/         # typed mock service layer (+ README on swapping to a real API)
    ├── mock/        # deterministic fictional dataset (28 issues, districts, fleet…)
    └── hooks/       # useAsync data-fetch hook
```

### Design tokens

- Semantic colors: CSS variables in `src/app/globals.css`, mapped in
  `tailwind.config.ts` (`primary` civic blue, `success` teal, `warning` amber,
  `destructive` vermilion, `navy` chrome).
- Chart & map colors: `src/lib/tokens.ts`. The damage-type palette was
  validated for color-vision-deficiency separation and contrast; legends and
  labels always accompany color.
- RDD-style class codes (D00/D10/D20/D40) exist only as internal data keys in
  `src/lib/types.ts`; the UI always shows plain-language damage-type names.

### Replacing mocks with the real ML API

All screens call `src/lib/api/index.ts`; nothing imports mock data directly.
Swap each function body for a `fetch` to the Python inference/backend service
while keeping the signatures — see `src/lib/api/README.md` for the full
contract and suggested endpoints. The map reads GeoJSON built in
`src/components/map/issue-map.tsx`, so live vector layers slot in there.

### Accessibility & motion

Keyboard-accessible Radix primitives, visible focus rings, ARIA labels on
icon-only controls, WCAG-conscious contrast, responsive from mobile to large
desktop, and `prefers-reduced-motion` support everywhere (animations collapse
to static states).
