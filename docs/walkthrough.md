# Walkthrough answers

Answers to the questions the brief says to expect.

## "A new store opens — what do you create?"

One record: a **`Maintenance Outlet`** (3-letter code + city). The city auto-resolves its
**`Zonal Office`**, so the store is immediately routable. Then either:

- run `PM Template.roll_out_to_outlet(outlet)` for each relevant `Asset Category`, **or**
- add `Store Asset` rows for the units the store actually has and roll templates onto them.

No PM tasks are re-typed — they come from the template. A new store is **1 outlet + N rollout
clicks**, not hundreds of manual schedule rows.

## "We move AC coil-cleaning to bi-monthly chain-wide — what do you touch?"

The **`PM Template` for Air Conditioner**, one row, change its `frequency`. That's the "define
once" point. (In this v1 the change applies to *new* rollouts/occurrences; existing live
`PM Schedule` rows can be bulk-updated with a one-line `frappe.db.set_value` loop or a small
patch — a natural next iteration would push template edits to open schedules automatically.)

## "How many records exist after a year, after five?"

The **master + schedule** rows are roughly constant — one `PM Schedule` per (asset, task), ~270
in the seed, scaling with stores × asset-types × tasks (low thousands at 133 stores). What grows
is **completion history and tickets**:

- A `PM Schedule` is rolled forward in place on completion (it does **not** spawn a new row per
  cycle), so schedule count stays flat. Completion *events* would live in a log/ledger if we add
  one.
- **Tickets** grow with incidents. At, say, 130 stores × a few tickets/store/month that's a few
  thousand/year, tens of thousands over five years — well within Frappe/MariaDB list-view scale,
  and partitionable by status/date.

So: masters flat, schedules flat, history/tickets linear. No combinatorial blow-up.

## "How would you route a ticket to the right technician?"

`outlet -> zonal_office -> technician`. On save, a ticket resolves the outlet's zonal office and
auto-assigns a technician in that office (`utils.pick_technician`): prefer the Maintenance
Incharge, else the active tech with the fewest open tickets (simple load-balancing). The assignee
gets a Frappe ToDo/assignment. Overdue PM escalates one step up the `reports_to` chain.
