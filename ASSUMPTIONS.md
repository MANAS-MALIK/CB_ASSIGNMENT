# Assumptions & Cut Scope

The data came from four systems and is messy. Per the brief, where it was ambiguous I made a
call, documented it here, and moved on.

## Data-cleaning calls

- **Asset-name aliases collapsed to 13 canonical `Asset Category` records.** The tracker had 20
  raw strings for ~13 real types (`AC` / `A/C Plant` / `Aircon Unit` / `Air Conditioner / AC Plant
  / FCU / AHU` -> **Air Conditioner**; `WIC` / `Walk-IN Chiller` / `Walk in Chiller` ->
  **Walk-in Chiller**; `Fire Ext.` / `Fire Extingushers` / `Fire Extinguisher` ->
  **Fire Extinguisher**; `Tortila Press` -> **Tortilla Press**). Mapping lives in
  `seed.ASSET_ALIASES`.
- **Blank-asset rows (18) -> `Facility (Store-level)` category.** These are agency/facility tasks
  (pest control etc.) not tied to a physical unit. Modelled as a pseudo-asset so they still
  schedule and route.
- **Frequency: 70% of rows were blank.** Provided values normalise cleanly
  (`Qtrly`->Quarterly, `6 month`->Half-Yearly). For blanks I **infer from tick cadence**:
  >=10 ticks->Monthly, 4-9->Quarterly, 2-3->Half-Yearly, <=1->Yearly. Heuristic, documented in
  `seed._infer_frequency`. One row literally says `freq?? ask maintenance` - flagged, defaulted.
- **Tick symbols `1`, `Y`, `✓` all mean "done".** Treated identically; used to back-fill
  `last_done` and infer frequency.
- **`Done By` names matched 100%** to the user master after normalising whitespace and trailing
  dots (`Santhosh .`, `Azad  Khan `). Stored as a link to `Maintenance Technician`.
- **Outlet codes & cities** in the tracker fully matched the outlet master (no orphans), so the
  joins are hard links.

## Structural calls

- **One unified `Asset Category`** powers both PM and tickets (the "one thing wearing two hats"
  question). PM tasks and reactive tickets point at the same taxonomy.
- **One `Store Asset` per (outlet, category)** by default — most stores run a single unit per
  type. `asset_tag` exists for stores that need to distinguish multiple units.
- **Zonal office derived from city code** (`BLR->Bengaluru`, `NCR->Delhi/NCR`, etc.). The
  **Mumbai** office has a technician (`Suraj Sahu`) but **no outlets** in the master — kept the
  office, noted the gap.
- **Only `Maintenance` dept staff are routable.** The 3 `Training` users and 1 `COR` user are
  imported but excluded from auto-assignment.
- **PM Schedules seeded from real (outlet, asset, task) combos** in the tracker (~270), not a full
  template-cross-join, so the demo data mirrors reality. Full rollout is available on demand via
  `PM Template.roll_out_to_all_outlets`.

## Cut scope (and why)

- **No mobile/field app or customer portal** — out of scope for a back-office v1.
- **No spare-parts inventory / stock levels** — the catalog is used only to *suggest* a part code
  on a ticket, not to track quantities. The source catalog was thin, so spare parts are generated
  from failure keywords (Gasket, Castor, Burner, ...).
- **No SLA timers / approval workflows on tickets** — status field only. Easy to add via Frappe
  workflow later.
- **Escalation is one level up** the `reports_to` chain on overdue, not a full multi-tier SLA.
- **Notifications use Frappe's Notification Log + ToDo assignment**, not email/WhatsApp — keeps it
  inside Frappe primitives and demoable without external config.
