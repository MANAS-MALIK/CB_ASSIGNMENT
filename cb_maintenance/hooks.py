app_name = "cb_maintenance"
app_title = "CB Maintenance"
app_publisher = "Manas Malik"
app_description = "Maintenance Operations (Planned PM + Reactive Tickets) for California Burrito."
app_email = "manas@example.com"
app_license = "mit"

# Scheduler: flag overdue PM schedules and notify the reporting chain daily.
scheduler_events = {
    "daily": [
        "cb_maintenance.cb_maintenance.tasks.refresh_pm_status_and_notify",
    ],
}
