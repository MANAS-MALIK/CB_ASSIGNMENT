"""Seed the CB Maintenance app from the case CSVs.

Run with:
    bench --site <site> execute cb_maintenance.cb_maintenance.seed.run

This is idempotent-ish: it skips records that already exist by name, so it can be
re-run safely. All the messy-data handling (asset aliases, frequency spellings,
tick symbols, name matching) lives here so the DocTypes stay clean.
"""

import csv
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

import frappe

from cb_maintenance.cb_maintenance.utils import next_due_from

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# --- Cleaning maps -------------------------------------------------------

# Raw asset string (lowercased, trimmed) -> canonical Asset Category.
ASSET_ALIASES = {
	"ac": "Air Conditioner",
	"a/c plant": "Air Conditioner",
	"aircon unit": "Air Conditioner",
	"air conditioner / ac plant / fcu / ahu": "Air Conditioner",
	"wic": "Walk-in Chiller",
	"walk-in chiller": "Walk-in Chiller",
	"walk in chiller": "Walk-in Chiller",
	"fire ext": "Fire Extinguisher",
	"fire extingushers": "Fire Extinguisher",
	"fire extinguisher": "Fire Extinguisher",
	"dg set & amf panel": "DG Set & AMF Panel",
	"ro plant": "RO Plant",
	"kitchen exhaust fan": "Kitchen Exhaust Fan",
	"hot line/warmer": "Hot Line / Warmer",
	"fryers": "Fryer",
	"tortila press": "Tortilla Press",
	"drain lines / grease trap": "Drain Lines / Grease Trap",
	"chest freezer": "Chest Freezer",
	"ice cube machine": "Ice Cube Machine",
}
FACILITY_CATEGORY = "Facility (Store-level)"

# Raw frequency string -> canonical frequency.
FREQUENCY_ALIASES = {
	"weekly": "Weekly",
	"monthly": "Monthly",
	"qtrly": "Quarterly",
	"quarterly": "Quarterly",
	"6 month": "Half-Yearly",
	"half-yearly": "Half-Yearly",
	"yearly": "Yearly",
}

# Tick symbols that all mean "done".
DONE_SYMBOLS = {"1", "Y", "y", "\u2713", "\u2714"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# City code -> zonal office name (derived from the user master "Home" values).
CITY_TO_OFFICE = {
	"BLR": "Bengaluru",
	"NCR": "Delhi/NCR",
	"HYD": "Hyderabad",
	"CHN": "Chennai",
	"PUN": "Pune",
	"MUM": "Mumbai",
}
OFFICE_CODE = {v: k for k, v in CITY_TO_OFFICE.items()}

# Spare-part keywords -> generated catalog (keyword matched against ticket sub-category).
SPARE_KEYWORDS = [
	("Gasket", "Door Gasket"),
	("Castor", "Castor Wheel"),
	("Caster", "Castor Wheel"),
	("Sheet", "Sealing Sheet"),
	("Burner", "Fryer Burner"),
	("Heater", "Heating Element"),
	("Compressor", "Compressor"),
	("Thermostat", "Thermostat"),
	("Filter", "RO Filter"),
]


def _read(name):
	# utf-8-sig strips a BOM if present so header keys stay clean (e.g. "Employee No").
	with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8-sig") as fh:
		return list(csv.DictReader(fh))


def _norm(s):
	return re.sub(r"\s+", " ", (s or "").strip().lower()).rstrip(".").strip()


def _parse_date(s):
	s = (s or "").strip()
	if not s:
		return None
	for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
		try:
			return datetime.strptime(s, fmt).date()
		except ValueError:
			continue
	return None


def _infer_frequency(row):
	"""Provided frequency wins; otherwise infer from how often the task was ticked."""
	raw = _norm(row.get("Freq"))
	if raw in FREQUENCY_ALIASES:
		return FREQUENCY_ALIASES[raw]
	ticks = sum(1 for m in MONTHS if (row.get(m) or "").strip() in DONE_SYMBOLS)
	if ticks >= 10:
		return "Monthly"
	if ticks >= 4:
		return "Quarterly"
	if ticks >= 2:
		return "Half-Yearly"
	return "Yearly"


def _canonical_asset(raw):
	key = _norm(raw)
	if not key:
		return FACILITY_CATEGORY
	return ASSET_ALIASES.get(key, raw.strip())


def _ensure(doctype, name, payload):
	if frappe.db.exists(doctype, name):
		return name
	doc = frappe.get_doc({"doctype": doctype, **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


# --- Seed steps ----------------------------------------------------------

def seed_zonal_offices():
	for office, code in OFFICE_CODE.items():
		_ensure("Zonal Office", office, {"zonal_office_name": office, "city_code": code})


def seed_technicians():
	users = _read("PM_Case_User_Master.csv")
	# Only maintenance staff are routable technicians; keep others out of assignment.
	name_to_emp = {}
	for u in users:
		emp = (u["Employee No"] or "").strip()
		if not emp:
			continue
		home = (u.get("Home") or "").strip()
		office = None
		for office_name in OFFICE_CODE:
			if office_name.lower() in home.lower():
				office = office_name
				break
		_ensure(
			"Maintenance Technician",
			emp,
			{
				"employee_no": emp,
				"technician_name": (u["Name"] or "").strip(),
				"job_title": (u.get("Job title") or "").strip(),
				"department": (u.get("Department") or "").strip(),
				"email": (u.get("Email") or "").strip(),
				"mobile": (u.get("Mobile") or "").strip(),
				"zonal_office": office,
				"is_active": 1,
			},
		)
		name_to_emp[_norm(u["Name"])] = emp

	# Second pass: wire up reports_to by matching the manager's name.
	for u in users:
		emp = (u["Employee No"] or "").strip()
		mgr_name = _norm(u.get("Reports to"))
		mgr_emp = name_to_emp.get(mgr_name)
		if emp and mgr_emp and mgr_emp != emp:
			frappe.db.set_value("Maintenance Technician", emp, "reports_to", mgr_emp)
	return name_to_emp


def seed_outlets():
	for o in _read("PM_Case_Outlets__Sheet1.csv"):
		code = (o["Outlet Code"] or "").strip()
		city = (o["City"] or "").strip()
		if not code:
			continue
		office = CITY_TO_OFFICE.get(city)
		_ensure(
			"Maintenance Outlet",
			code,
			{
				"outlet_code": code,
				"outlet_name": f"California Burrito {code}",
				"city": city,
				"zonal_office": office,
			},
		)


def seed_ticket_taxonomy_and_spares():
	rows = _read("PM_Case_Ticket_Buckets__Sheet1.csv")
	seen = set()
	for r in rows:
		dept = (r.get("Department") or "").strip()
		cat = (r.get("Category") or "").strip()
		sub = (r.get("Sub Category 1") or "").strip()
		if not dept or not cat:
			continue
		key = (dept, cat, sub)
		if key in seen:
			continue
		seen.add(key)
		if not frappe.db.exists("Ticket Category", {"department": dept, "category": cat, "sub_category": sub}):
			frappe.get_doc(
				{
					"doctype": "Ticket Category",
					"department": dept,
					"category": cat,
					"sub_category": sub,
				}
			).insert(ignore_permissions=True)

	# Build a small coded spare-parts catalog keyed by failure keywords.
	for keyword, part_name in SPARE_KEYWORDS:
		code = "SP-" + keyword.upper()
		_ensure(
			"Spare Part",
			code,
			{"part_code": code, "part_name": part_name, "match_keyword": keyword},
		)


def seed_pm_program():
	"""Build Asset Categories + PM Templates + Store Assets + PM Schedules from the tracker."""
	rows = _read("PM_Case_Before__PM_Tracker_2026.csv")
	users = _read("PM_Case_User_Master.csv")
	name_to_emp = {_norm(u["Name"]): (u["Employee No"] or "").strip() for u in users}

	# Collect canonical categories and template tasks.
	template_tasks = defaultdict(dict)  # category -> {task: Counter(frequency)}
	for r in rows:
		category = _canonical_asset(r.get("Asset"))
		task = (r.get("Task") or "").strip()
		if not task:
			continue
		freq = _infer_frequency(r)
		is_inspection = 1 if re.search(r"check|inspect|measure", task, re.I) else 0
		template_tasks[category].setdefault(task, {"freq": Counter(), "insp": is_inspection})
		template_tasks[category][task]["freq"][freq] += 1

	# Asset categories
	for category in template_tasks:
		_ensure("Asset Category", category, {"category_name": category})

	# PM Templates (one per category, tasks deduped with majority frequency)
	for category, tasks in template_tasks.items():
		tname = f"{category} - Standard PM"
		if frappe.db.exists("PM Template", tname):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "PM Template",
				"template_name": tname,
				"asset_category": category,
				"is_active": 1,
				"tasks": [
					{
						"task": task,
						"frequency": meta["freq"].most_common(1)[0][0],
						"is_inspection": meta["insp"],
					}
					for task, meta in tasks.items()
				],
			}
		)
		doc.insert(ignore_permissions=True)

	# Store Assets + PM Schedules from actual outlet/asset/task combos in the tracker.
	created = 0
	for r in rows:
		outlet = (r.get("Outlet") or "").strip()
		task = (r.get("Task") or "").strip()
		if not outlet or not task or not frappe.db.exists("Maintenance Outlet", outlet):
			continue
		category = _canonical_asset(r.get("Asset"))
		asset_name = f"{outlet}-{category}"
		if not frappe.db.exists("Store Asset", asset_name):
			frappe.get_doc(
				{
					"doctype": "Store Asset",
					"outlet": outlet,
					"asset_category": category,
				}
			).insert(ignore_permissions=True)

		if frappe.db.exists("PM Schedule", {"store_asset": asset_name, "task": task}):
			continue

		freq = _infer_frequency(r)
		last_done = _parse_date(r.get("Last Done"))
		done_by_emp = name_to_emp.get(_norm(r.get("Done By")))
		base = last_done or datetime.today().date()
		frappe.get_doc(
			{
				"doctype": "PM Schedule",
				"store_asset": asset_name,
				"task": task,
				"frequency": freq,
				"is_inspection": 1 if re.search(r"check|inspect|measure", task, re.I) else 0,
				"last_done": last_done,
				"last_done_by": done_by_emp if done_by_emp and frappe.db.exists("Maintenance Technician", done_by_emp) else None,
				"next_due": next_due_from(base, freq),
			}
		).insert(ignore_permissions=True)
		created += 1
	return created


def run():
	"""Entry point. Order matters because of links."""
	seed_zonal_offices()
	name_to_emp = seed_technicians()

	# Wire zonal-office managers to the highest-ranking tech in each office.
	for office in OFFICE_CODE:
		lead = frappe.get_all(
			"Maintenance Technician",
			filters={"zonal_office": office, "is_active": 1},
			fields=["name", "job_title"],
		)
		if lead:
			pref = [t for t in lead if "incharge" in (t.job_title or "").lower() or "manager" in (t.job_title or "").lower()]
			frappe.db.set_value("Zonal Office", office, "manager", (pref or lead)[0].name)

	seed_outlets()
	seed_ticket_taxonomy_and_spares()
	created = seed_pm_program()

	frappe.db.commit()
	print(f"Seed complete. PM Schedules created: {created}")
	_print_counts()


def create_reviewer(email="reviewer@californiaburrito.in", password="Review@2026"):
	"""Create a System Manager login for reviewers to click through the site."""
	if frappe.db.exists("User", email):
		print(f"Reviewer already exists: {email}")
		return email
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "CB",
			"last_name": "Reviewer",
			"send_welcome_email": 0,
			"new_password": password,
		}
	)
	user.insert(ignore_permissions=True)
	user.add_roles("System Manager")
	frappe.db.commit()
	print(f"Created reviewer {email} / {password}")
	return email


def _print_counts():
	print(
		"Counts:",
		{
			dt: frappe.db.count(dt)
			for dt in [
				"Zonal Office",
				"Maintenance Technician",
				"Maintenance Outlet",
				"Asset Category",
				"PM Template",
				"Store Asset",
				"PM Schedule",
				"Ticket Category",
				"Spare Part",
			]
		},
	)
