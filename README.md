# CB Maintenance

A Frappe app that replaces California Burrito's spreadsheet-based equipment maintenance with a
proper data model covering both the **planned** (preventive maintenance) and **unplanned**
(reactive tickets) worlds, sharing one equipment taxonomy and one reporting chain.

> Build exercise submission. See `ASSUMPTIONS.md` for the calls made on ambiguous data and
> `docs/walkthrough.md` for answers to the walkthrough questions.

## What it does (v1)

1. **Define the PM program once** — a `PM Template` per `Asset Category` lists the tasks and how
   often each is due. Rolling it onto a store creates `Store Asset` + `PM Schedule` rows without
   re-entering tasks per store.
2. **Due / Overdue + mark done** — `PM Schedule` tracks `last_done` / `next_due` / `status`. A
   daily scheduler flags overdue items. "Mark Done" rolls `next_due` forward by the frequency.
3. **Reactive tickets** — `Maintenance Ticket` is raised against an outlet (and optionally a
   specific asset), classified by the `Dept -> Category -> Sub Category` taxonomy.
4. **Graceful messy data** — the importer normalises asset-name aliases, frequency spellings and
   tick symbols, and matches `Done By` names back to technicians.

## Go further (built, not gestured at)

- **Auto-routing**: outlet -> city -> `Zonal Office` -> technicians. A new ticket (or overdue PM)
  is auto-assigned to a technician in the outlet's zonal office, and escalation walks the
  `reports_to` chain.
- **Unified taxonomy**: planned and unplanned share `Asset Category`, so a PM task and a ticket on
  the same chiller point at the same equipment type.
- **Spare-part suggestion**: a ticket sub-category like "Gasket Broken" surfaces the matching
  `Spare Part` code.

## Install

```bash
# on a Frappe v15 bench
bench get-app cb_maintenance <repo-url>
bench --site <site> install-app cb_maintenance
bench --site <site> migrate
# seed masters + demo data from the case CSVs
bench --site <site> execute cb_maintenance.cb_maintenance.seed.run
```

## Deploy to Frappe Cloud (live link deliverable)

1. Push this app to a public GitHub repo.
2. Frappe Cloud -> New Bench -> add this app from the GitHub URL.
3. Create a site, install the app, run the seed command above from the bench console.
4. Create a login for the reviewers (Desk user) and share the site URL + credentials.
