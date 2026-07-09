# Game Client

[`app/src/BartGame.tsx`](https://github.com/aslmylmz/open-bart/blob/main/app/src/BartGame.tsx)
is a self-contained React component (bundled by Vite into a static SPA) that
administers the dynamic-hazard BART and captures pump-level telemetry. Its UI
strings are in Turkish, matching the reference study's cohort.

## Component contract

```tsx
import BartGame from "./BartGame";

<BartGame
  candidateId="participant-123"
  onComplete={(result) => {
    // result is the scored AssessmentResult returned by your backend
  }}
/>
```

```{list-table}
:header-rows: 1
:widths: 24 20 56

* - Prop
  - Type
  - Purpose
* - `candidateId`
  - `string`
  - Identifier attached to the submitted session.
* - `onComplete`
  - `(data: AssessmentResult) => void` *(optional)*
  - Called with the scored result after submission. When provided, the final button reads "Next" instead of "See my results"; when omitted, the component shows its own results screen.
```

## Session generation

`generateSessionConfig()` builds 30 balloons — 10 each of orange, teal, and
purple — then shuffles them with a Fisher–Yates pass. Each balloon stores its
color and `maxPumps` ($N$ = 8 / 32 / 128).

## The explosion model

The client implements exactly the same hazard rule as the scoring engine. On the
$k$-th pump of a balloon with capacity $N$:

```ts
const explosionProbability = newPumps / maxPumps;          // k / N
const explode = newPumps >= maxPumps || Math.random() < explosionProbability;
```

The `newPumps >= maxPumps` guard caps the balloon at $N$, mirroring the engine's
distribution cap.

## Event logging

Every action appends a {py:class}`~scoring.schemas.GameEvent`-shaped record to an
in-memory log with a high-resolution monotonic timestamp:

```ts
eventLogRef.current.push({
  timestamp: performance.now(),
  type,                                 // "pump" | "collect" | "explode"
  payload: { balloon_id, color, ...extra },
});
```

`performance.now()` is used (not `Date.now()`) for sub-millisecond, monotonic
timing — which is what the engine's latency and auto-repeat checks rely on.

Controls: **Space** pumps, **Enter** collects. Each collected pump is worth
\$0.25; a burst forfeits the balloon.

## Submission

On completion the component POSTs the session to a backend endpoint:

```ts
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
await fetch(`${apiUrl}/assessments/bart`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    session_id,            // crypto.randomUUID()
    game_type: "BART_RISK",
    candidate_id,
    events,                // the full GameEvent[] log
  }),
});
```

The POST body matches the {py:class}`~scoring.schemas.GameSession` schema exactly.

:::{admonition} The scoring endpoint is yours to provide
:class: important

This repository ships the **game client** and the **scoring engine** as reusable
parts, but not the HTTP server that connects them. The client expects a backend
that accepts the `GameSession` payload at `POST /assessments/bart`, runs
{py:func}`scoring.bart.score_bart`, and returns an `AssessmentResult`. A minimal
adapter (e.g. FastAPI) looks like:

```python
from fastapi import FastAPI
from scoring.schemas import GameSession
from scoring.bart import score_bart

app = FastAPI()

@app.post("/assessments/bart")
def score(session: GameSession):
    metrics = score_bart(session.events)
    return {
        "session_id": session.session_id,
        "game_type": session.game_type,
        "candidate_id": session.candidate_id,
        "raw_metrics": metrics.model_dump(),
        "normalized_scores": [],   # fill in against your population norms
    }
```

The `normalized_scores` and `profile_traits` fields the client renders are
population-relative and depend on norms you supply; they are optional and may be
returned empty.
:::
