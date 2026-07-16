# Service layer — replacing mocks with the real ML API

All screens call the typed functions in `src/lib/api/index.ts`. Nothing in the
UI imports `src/lib/mock/*` directly, so the mock layer can be swapped for the
Python inference/backend API without touching components.

## How to swap

1. Keep the function signatures and the types in `src/lib/types.ts`.
2. Replace each function body with a `fetch` to your backend, e.g.:

```ts
export async function getIssues(filters: IssueFilters = {}): Promise<RoadIssue[]> {
  const res = await fetch(`${API_BASE}/issues?${toQuery(filters)}`);
  if (!res.ok) throw new Error(`Issues request failed: ${res.status}`);
  return (await res.json()) as RoadIssue[];
}
```

3. Map backend fields to the domain models in one place (a `mapIssue(dto)`
   helper) if the Python API uses different field names.
4. Delete `src/lib/mock/*` once every function is backed by the API.

## Suggested future endpoints (not implemented anywhere yet)

These are placeholders for planning only — the prototype never calls a network
API and never claims results came from a live model.

| Function              | Future backend responsibility                        |
| --------------------- | ---------------------------------------------------- |
| `getIssues`           | filtered detection list (post-NMS, with geodata)     |
| `getIssue`            | single detection with bounding boxes                 |
| `setIssueReview`      | human review verdict (confirm / reject), audit-logged|
| `createWorkOrder`     | work-order creation in the city's AMS                |
| `getDashboardStats`   | aggregate metrics per municipality + date range      |
| `getTrends`           | monthly rollups                                      |
| `mockDetectionsForUpload` | replace with real `POST /infer` on the PyTorch service |

The ingestion screen's processing pipeline is simulated client-side and is
labeled as such in the UI.
