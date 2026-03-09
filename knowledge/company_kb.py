"""Company Knowledge Base — Per-client solar company information.

Each solar company client gets their own knowledge record in the database.
The voice agent and email agent inject this context into every interaction,
making the AI deeply knowledgeable about the specific company it represents.

Storage: SQLite (hot) + JSON files (warm) for rich content like FAQs.

Usage:
    from knowledge.company_kb import get_kb_for_agent, seed_demo_company

    kb = get_kb_for_agent("suntech_solar")
    # Returns full context string ready to inject into system prompt
"""

import json
import logging
import os
from datetime import datetime
from memory.database import get_conn, fetch_all, fetch_one, insert, update

logger = logging.getLogger(__name__)

KB_DIR = os.path.join(os.path.dirname(__file__), "clients")
os.makedirs(KB_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE SCHEMA (extends existing db — init called from database.py)
# ─────────────────────────────────────────────────────────────────────────────

def init_kb_tables():
    """Create knowledge base tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS company_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                client_id TEXT UNIQUE NOT NULL,
                company_name TEXT NOT NULL,
                abn TEXT,
                phone TEXT,
                email TEXT,
                website TEXT,
                service_areas TEXT,
                years_in_business INTEGER DEFAULT 0,
                num_installers INTEGER DEFAULT 0,
                certifications TEXT,
                ghl_location_id TEXT,
                retell_agent_id TEXT,
                elevenlabs_voice_id TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS company_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                product_type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                price_from_aud REAL,
                price_to_aud REAL,
                features TEXT,
                brands TEXT,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS company_faqs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                category TEXT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                priority INTEGER DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS company_objections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                objection TEXT NOT NULL,
                response TEXT NOT NULL,
                priority INTEGER DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS rebate_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                scheme_name TEXT NOT NULL,
                description TEXT,
                amount_per_kw REAL,
                max_amount REAL,
                expiry_date TEXT,
                eligibility TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
    print("[KB] Knowledge base tables ready.")


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE CRUD
# ─────────────────────────────────────────────────────────────────────────────

def upsert_company(client_id: str, data: dict) -> int:
    """Create or update a company profile.

    Args:
        client_id: Unique identifier for this client (e.g. 'suntech_solar')
        data: Company profile fields

    Returns:
        Row ID of created/updated record
    """
    existing = fetch_one("SELECT id FROM company_profiles WHERE client_id = ?", (client_id,))
    if existing:
        with get_conn() as conn:
            fields = {k: v for k, v in data.items() if k != "client_id"}
            fields["updated_at"] = datetime.utcnow().isoformat()
            assigns = ", ".join(f"{k} = ?" for k in fields)
            values  = list(fields.values()) + [client_id]
            conn.execute(f"UPDATE company_profiles SET {assigns} WHERE client_id = ?", values)
        print(f"[KB] Updated company profile: {client_id}")
        return existing["id"]
    else:
        row_id = insert("company_profiles", {"client_id": client_id, **data})
        print(f"[KB] Created company profile: {client_id} (id={row_id})")
        return row_id


def get_company(client_id: str) -> dict:
    """Fetch a company profile.

    Args:
        client_id: Client identifier

    Returns:
        Company profile dict or empty dict
    """
    return fetch_one("SELECT * FROM company_profiles WHERE client_id = ?", (client_id,))


def add_product(client_id: str, product_data: dict) -> int:
    """Add a product/service to a company's knowledge base.

    Args:
        client_id: Client identifier
        product_data: Product fields (product_type, name, description, price_from_aud, etc.)

    Returns:
        Row ID
    """
    return insert("company_products", {"client_id": client_id, **product_data})


def add_faq(client_id: str, question: str, answer: str, category: str = "general", priority: int = 5) -> int:
    """Add a FAQ entry for a company.

    Args:
        client_id: Client identifier
        question: The question text
        answer: The answer text
        category: FAQ category (pricing, process, technical, rebates)
        priority: Sort priority (1=highest)

    Returns:
        Row ID
    """
    return insert("company_faqs", {
        "client_id": client_id,
        "question": question,
        "answer": answer,
        "category": category,
        "priority": priority,
    })


def add_objection(client_id: str, objection: str, response: str, priority: int = 5) -> int:
    """Add an objection handler for a company's voice agent.

    Args:
        client_id: Client identifier
        objection: The objection text (e.g. 'I need to think about it')
        response: Recommended response
        priority: Sort priority

    Returns:
        Row ID
    """
    return insert("company_objections", {
        "client_id": client_id,
        "objection": objection,
        "response": response,
        "priority": priority,
    })


def upsert_rebate(state: str, scheme_name: str, data: dict):
    """Add or update a government rebate scheme.

    Args:
        state: Australian state code (QLD, WA, SA, etc.)
        scheme_name: Name of the rebate scheme
        data: Rebate details
    """
    existing = fetch_one(
        "SELECT id FROM rebate_info WHERE state = ? AND scheme_name = ?",
        (state, scheme_name)
    )
    if existing:
        with get_conn() as conn:
            conn.execute(
                "UPDATE rebate_info SET description=?, amount_per_kw=?, max_amount=?, expiry_date=?, eligibility=?, updated_at=? WHERE id=?",
                (data.get("description"), data.get("amount_per_kw"), data.get("max_amount"),
                 data.get("expiry_date"), data.get("eligibility"),
                 datetime.utcnow().isoformat(), existing["id"])
            )
    else:
        insert("rebate_info", {"state": state, "scheme_name": scheme_name, **data})


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT BUILDER — injects into AI agent system prompts
# ─────────────────────────────────────────────────────────────────────────────

def get_kb_for_agent(client_id: str) -> str:
    """Build a complete knowledge base context string for AI agent injection.

    This is the main function used by voice and email agents.
    Returns a formatted string containing all company knowledge.

    Args:
        client_id: Client identifier

    Returns:
        Formatted knowledge base string for system prompt injection
    """
    profile  = get_company(client_id) or {}
    products = fetch_all("SELECT * FROM company_products WHERE client_id = ? AND active = 1", (client_id,))
    faqs     = fetch_all("SELECT * FROM company_faqs WHERE client_id = ? ORDER BY priority", (client_id,))
    objs     = fetch_all("SELECT * FROM company_objections WHERE client_id = ? ORDER BY priority", (client_id,))

    # Load state-specific rebate info
    service_areas = profile.get("service_areas", "") or ""
    states = [s.strip().upper() for s in service_areas.split(",") if s.strip()]
    rebates = []
    for state in states:
        r = fetch_all("SELECT * FROM rebate_info WHERE state = ? ORDER BY amount_per_kw DESC", (state,))
        rebates.extend(r)

    sections = []

    # ── Company identity
    sections.append(f"""COMPANY PROFILE
===============
Company:        {profile.get('company_name', 'Your Solar Company')}
ABN:            {profile.get('abn', 'Not provided')}
Phone:          {profile.get('phone', 'Not provided')}
Email:          {profile.get('email', 'Not provided')}
Website:        {profile.get('website', 'Not provided')}
Service Areas:  {profile.get('service_areas', 'Australia-wide')}
Years Active:   {profile.get('years_in_business', '?')} years
Team Size:      {profile.get('num_installers', '?')} installers
Certifications: {profile.get('certifications', 'Clean Energy Council Approved')}""")

    # ── Products & pricing
    if products:
        prod_lines = ["", "PRODUCTS & PRICING", "=================="]
        for p in products:
            price_range = ""
            if p.get("price_from_aud") and p.get("price_to_aud"):
                price_range = f" — ${p['price_from_aud']:,.0f}–${p['price_to_aud']:,.0f} after rebates"
            elif p.get("price_from_aud"):
                price_range = f" — from ${p['price_from_aud']:,.0f} after rebates"
            prod_lines.append(f"\n{p.get('product_type','').upper()}: {p.get('name','')}{price_range}")
            if p.get("description"):
                prod_lines.append(f"  {p['description']}")
            if p.get("brands"):
                prod_lines.append(f"  Brands: {p['brands']}")
            if p.get("features"):
                try:
                    feats = json.loads(p["features"]) if isinstance(p["features"], str) else p["features"]
                    prod_lines.append(f"  Includes: {', '.join(feats)}")
                except Exception:
                    prod_lines.append(f"  Features: {p['features']}")
        sections.append("\n".join(prod_lines))

    # ── Government rebates
    if rebates:
        reb_lines = ["", "GOVERNMENT REBATES & INCENTIVES", "================================"]
        seen = set()
        for r in rebates:
            key = f"{r.get('state')}-{r.get('scheme_name')}"
            if key in seen:
                continue
            seen.add(key)
            reb_lines.append(f"\n{r.get('state')} — {r.get('scheme_name')}")
            reb_lines.append(f"  {r.get('description', '')}")
            if r.get("amount_per_kw"):
                reb_lines.append(f"  Value: ~${r['amount_per_kw']:,.0f}/kW")
            if r.get("max_amount"):
                reb_lines.append(f"  Max:   ${r['max_amount']:,.0f}")
            if r.get("eligibility"):
                reb_lines.append(f"  Who:   {r['eligibility']}")
        sections.append("\n".join(reb_lines))

    # ── Standard Australian STC info (always included)
    sections.append("""
FEDERAL REBATE — SMALL-SCALE TECHNOLOGY CERTIFICATES (STCs)
============================================================
All eligible Australian homes receive STCs (fed rebate) based on system size and location.
A 6.6kW system typically earns ~$2,500–$4,000 in STC value, applied as an upfront discount.
Owner-occupiers who are electricity customers are eligible. Renters are NOT eligible for STCs.
The STC value varies by installation year and zone — we calculate the exact amount during your quote.""")

    # ── FAQs
    if faqs:
        faq_lines = ["", "FREQUENTLY ASKED QUESTIONS", "=========================="]
        for f in faqs:
            if f.get("category"):
                faq_lines.append(f"\n[{f['category'].upper()}]")
            faq_lines.append(f"Q: {f['question']}")
            faq_lines.append(f"A: {f['answer']}")
        sections.append("\n".join(faq_lines))
    else:
        sections.append(_default_faqs())

    # ── Objection handlers
    if objs:
        obj_lines = ["", "OBJECTION HANDLERS", "=================="]
        for o in objs:
            obj_lines.append(f"\nIF CUSTOMER SAYS: \"{o['objection']}\"")
            obj_lines.append(f"RESPOND WITH: {o['response']}")
        sections.append("\n".join(obj_lines))
    else:
        sections.append(_default_objections(profile.get("company_name", "us")))

    # ── Sales process
    sections.append(_sales_process())

    return "\n\n".join(sections)


def get_rebate_for_state(state: str, system_size_kw: float = 6.6) -> str:
    """Return a human-readable rebate summary for a given state and system size.

    Args:
        state: Australian state code
        system_size_kw: Estimated system size in kW

    Returns:
        Rebate summary string
    """
    state = state.upper()
    rebates = fetch_all("SELECT * FROM rebate_info WHERE state = ?", (state,))

    lines = [f"Rebates available in {state} for a {system_size_kw}kW system:"]

    # Federal STC estimate
    stc_value = system_size_kw * 450  # rough AUD estimate
    lines.append(f"  Federal STC rebate: ~${stc_value:,.0f} (applied as upfront discount)")

    for r in rebates:
        amt = (r.get("amount_per_kw") or 0) * system_size_kw
        lines.append(f"  {r['scheme_name']}: ~${amt:,.0f} ({r.get('description', '')})")

    if not rebates:
        lines.append("  No additional state rebates currently active in your area.")

    lines.append("  Total potential savings applied at point of sale — no paperwork needed.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT CONTENT (used when company hasn't filled in their KB yet)
# ─────────────────────────────────────────────────────────────────────────────

def _default_faqs() -> str:
    return """
FREQUENTLY ASKED QUESTIONS
==========================

[PROCESS]
Q: How long does the whole process take from call to installation?
A: Typically 2–6 weeks: site assessment (week 1), proposal (week 1–2), council/grid approval (week 2–4), installation (half a day).

Q: Do I need council approval?
A: In most cases no. Standard residential rooftop solar under 10kW is exempt from DA in most Australian states. We handle all grid connection paperwork.

[PRICING]
Q: How much does solar cost?
A: After government rebates (STCs), a quality 6.6kW system typically costs $4,500–$7,000 installed. We'll give you an exact quote after assessing your roof.

Q: Can I pay in installments?
A: Yes — we offer 0% interest finance over 24 months and solar loans through our finance partners. Most customers find the loan repayment is less than their current bill.

Q: Is the quote free?
A: Absolutely. Your assessment and proposal are completely free and no obligation.

[TECHNICAL]
Q: What brands of panels and inverters do you use?
A: We install Tier 1 panels — brands like REC, Jinko, Canadian Solar — paired with Fronius, SMA, or SolarEdge inverters. All come with full manufacturer warranties.

Q: What's the warranty?
A: Panels: 25-year performance warranty. Inverter: 5–10 years. Workmanship: 5 years on our installation.

Q: Will it work on cloudy days?
A: Yes. Solar still generates power on overcast days — typically 10–25% of full output. Australia's average sunshine means most systems produce 80–100% of their design output annually.

Q: How much will I actually save?
A: Most of our WA customers save $1,200–$2,500 per year depending on their usage. We'll show you an exact payback period in your proposal — typically 3–6 years.

[BATTERIES]
Q: Do I need a battery?
A: Not required but highly recommended if you're away during the day or want energy independence. A 10kWh battery adds $8,000–$12,000 but lets you use solar power at night.

Q: What battery do you recommend?
A: We install Tesla Powerwall, BYD, and Sungrow batteries — all with 10-year warranties. We'll recommend the right size based on your usage patterns."""


def _default_objections(company_name: str) -> str:
    return f"""
OBJECTION HANDLERS
==================

IF CUSTOMER SAYS: "I need to think about it"
RESPOND WITH: Completely understand — it's a significant decision. Would it help if I sent you a summary with our typical payback periods and savings calculations? Most customers find seeing the numbers makes it much clearer. What email should I send it to?

IF CUSTOMER SAYS: "It's too expensive"
RESPOND WITH: That's a fair concern. Before your assessment you won't know the actual post-rebate price — many customers are surprised how affordable it is after the federal rebate. Can I book a free site assessment so we can give you an exact number? There's no obligation at all.

IF CUSTOMER SAYS: "I'll wait until prices come down"
RESPOND WITH: Prices have actually been stable for the past two years after dropping 80% over the previous decade. The bigger risk is waiting — the federal rebate reduces each year, so waiting typically costs an extra $200–400 annually. The best time to lock in your savings is now.

IF CUSTOMER SAYS: "I'm renting"
RESPOND WITH: Unfortunately as a renter you wouldn't be eligible for the federal rebate — that goes to the property owner. It's worth speaking to your landlord though, as solar can increase their property value and make the home more attractive to tenants. Is there anything else I can help with?

IF CUSTOMER SAYS: "I've already got quotes"
RESPOND WITH: Great — that means you're serious about it. We'd love the chance to present our quote too. We're known for our quality workmanship and post-install support. A quick 20-minute assessment means we can give you an accurate, apples-to-apples comparison. When works for you?

IF CUSTOMER SAYS: "I'm not interested"
RESPOND WITH: No problem at all. Just so you know, if your situation changes — electricity bills are forecast to rise another 15-20% over the next two years — we're always here. Can I ask what's putting you off today? That feedback helps us improve."""


def _sales_process() -> str:
    return """
OUR SALES PROCESS — HOW IT WORKS
==================================
Step 1: DISCOVERY CALL (NOW)
  Understand the customer's situation: bill, roof, goals, timeline.
  Goal: Book a free site assessment or get email to send proposal.

Step 2: FREE SITE ASSESSMENT (1-3 days)
  Our installer visits, measures roof, checks switchboard, photos everything.
  Duration: 30–45 minutes. No obligation.

Step 3: PROPOSAL (within 48 hours of assessment)
  Tailored system design, exact pricing, payback period, savings projection.
  Sent by email + followed up by phone.

Step 4: CONTRACT SIGNING
  If happy, customer signs digitally. Deposit: typically 10%.

Step 5: APPROVALS (2–4 weeks)
  We lodge grid connection (Synergy/AusGrid etc.) + any council permits.
  Customer does nothing — we handle all paperwork.

Step 6: INSTALLATION (half day)
  Clean install by our CEC-accredited team. Grid connection activated.

Step 7: HANDOVER & SUPPORT
  We walk you through the monitoring app. Ongoing support via phone/email.

CALL OBJECTIVE — QUALIFY AND BOOK:
  Collect: homeowner status, monthly bill, roof type/age, preferred time for assessment.
  Book: a free site assessment appointment OR get email for digital proposal.
  Never pressure — focus on education and value."""


# ─────────────────────────────────────────────────────────────────────────────
# DEMO SEEDER
# ─────────────────────────────────────────────────────────────────────────────

def seed_demo_company(client_id: str = "suntech_solar_perth"):
    """Seed a realistic demo solar company for testing.

    Args:
        client_id: Client identifier to use
    """
    init_kb_tables()

    upsert_company(client_id, {
        "company_name": "SunTech Solar Perth",
        "abn": "12 345 678 901",
        "phone": "08 9XXX XXXX",
        "email": "info@suntechsolar.com.au",
        "website": "https://suntechsolar.com.au",
        "service_areas": "WA, Perth Metro, Mandurah, Joondalup, Fremantle",
        "years_in_business": 8,
        "num_installers": 12,
        "certifications": "Clean Energy Council Approved Retailer, SunPower Elite Dealer, Tesla Powerwall Certified",
    })

    add_product(client_id, {
        "product_type": "solar_system",
        "name": "Standard Home Solar — 6.6kW",
        "description": "Our most popular system. Suits 3–4 bedroom homes with bills over $200/mo.",
        "price_from_aud": 4500,
        "price_to_aud": 6500,
        "brands": "REC, Jinko, Canadian Solar + Fronius or SolarEdge inverter",
        "features": json.dumps(["25yr panel warranty", "5yr workmanship warranty", "Remote monitoring app", "Grid connect included"]),
    })

    add_product(client_id, {
        "product_type": "solar_system",
        "name": "Large Home Solar — 10kW",
        "description": "For bigger homes or high-usage households. Bills over $400/mo.",
        "price_from_aud": 7000,
        "price_to_aud": 10000,
        "brands": "REC Alpha, SunPower + SolarEdge",
        "features": json.dumps(["25yr panel warranty", "10yr inverter warranty", "Optimiser per panel", "Battery-ready"]),
    })

    add_product(client_id, {
        "product_type": "battery",
        "name": "Tesla Powerwall 2 — 13.5kWh",
        "description": "Store solar energy for night use. Backup power during outages.",
        "price_from_aud": 12000,
        "price_to_aud": 14000,
        "brands": "Tesla",
        "features": json.dumps(["10yr warranty", "Backup gateway included", "App monitoring", "VPP eligible"]),
    })

    add_product(client_id, {
        "product_type": "ev_charger",
        "name": "EV Charger — 7.2kW Home Charger",
        "description": "Charge your EV with your own solar. Full charge overnight.",
        "price_from_aud": 1200,
        "price_to_aud": 2000,
        "brands": "Zappi, Wallbox",
        "features": json.dumps(["Solar-optimised charging", "App control", "5yr warranty"]),
    })

    upsert_rebate("WA", "Synergy Buyback Scheme", {
        "description": "Excess solar exported to the grid earns 2.25c–10c/kWh from Synergy (WA's retailer).",
        "amount_per_kw": 0,
        "max_amount": None,
        "eligibility": "WA homeowners connected to Synergy network",
    })

    upsert_rebate("WA", "Federal STC Rebate", {
        "description": "Small-Scale Technology Certificates reduce upfront cost. Based on system size and zone.",
        "amount_per_kw": 450,
        "max_amount": 4000,
        "eligibility": "Owner-occupiers, landlords. System must be installed by CEC-accredited installer.",
    })

    # FAQs — process
    add_faq(client_id, "What areas do you service?",
            "We service all of Perth metro including Joondalup, Mandurah, Fremantle, and surrounding suburbs.", "general", 1)
    add_faq(client_id, "How long have you been in business?",
            "SunTech Solar has been installing solar in Perth since 2017 — over 8 years and 2,400+ installations.", "general", 1)
    add_faq(client_id, "Are you CEC approved?",
            "Yes — we're a Clean Energy Council Approved Retailer, which means you're protected by the CEC Consumer Code.", "general", 2)
    add_faq(client_id, "How long does the whole process take from call to installation?",
            "Typically 3–6 weeks: free site assessment in the first week, your tailored proposal within 48 hours, then grid connection approvals take 2–4 weeks, and installation is usually just half a day.",
            "process", 2)
    add_faq(client_id, "Do I need council approval?",
            "In most cases no — standard residential rooftop solar under 10kW is exempt from development approval in WA. We handle all grid connection paperwork with Synergy on your behalf.",
            "process", 3)

    # FAQs — pricing
    add_faq(client_id, "How much does a solar system cost?",
            "After the federal rebate (STCs), a quality 6.6kW system typically costs $4,500–$6,500 installed in Perth. We'll give you an exact quote after our free site assessment.",
            "pricing", 2)
    add_faq(client_id, "Do you offer finance?",
            "Yes — we offer interest-free options over 24 months and solar loans through our finance partners. Most customers find the monthly repayment is less than their current power bill.",
            "pricing", 3)

    # FAQs — technical
    add_faq(client_id, "What brands do you install?",
            "We install Tier 1 panels — REC, Jinko, and Canadian Solar — paired with Fronius, SolarEdge, or SMA inverters. All come with full manufacturer warranties direct from the brand.",
            "technical", 3)

    # Objections
    add_objection(client_id,
        "It's too expensive",
        "That's a fair concern. Before your site assessment you won't know your actual post-rebate price — many Perth customers are genuinely surprised how affordable it is. The federal rebate alone takes $2,500–$4,000 off upfront. Can I book a free, no-obligation assessment so we can give you an exact number?",
        1)
    add_objection(client_id,
        "I need to think about it",
        "Completely understand — it's a significant investment. Would it help if I sent you a summary showing typical Perth payback periods and savings? Most customers find seeing the numbers makes the decision much clearer. What email should I send it to?",
        2)
    add_objection(client_id,
        "I'll wait until prices come down more",
        "Prices have been stable for the past two years after dropping 80% over the previous decade. The bigger risk now is waiting — the federal STC rebate reduces each year, so holding off typically costs an extra $200–$400. The best time to lock in your savings is before the next deeming period drop.",
        3)
    add_objection(client_id,
        "I'm renting",
        "As a renter you unfortunately wouldn't be eligible for the federal rebate — that goes to the property owner. It's worth a conversation with your landlord though — solar increases property value and can make a home more attractive to tenants long-term. Is there anything else I can help with?",
        4)
    add_objection(client_id,
        "I've already got quotes from other companies",
        "Great — that means you're serious about it. We'd love the opportunity to present our quote too. We're known for quality workmanship and 5-year installation warranty. A quick 30-minute assessment means we can give you an accurate apples-to-apples comparison. When suits you?",
        5)
    add_objection(client_id,
        "I'm not interested",
        "No problem at all. Just so you know — electricity prices in WA are forecast to rise another 15–20% over the next two years, so if your situation changes we're always here. May I ask what's putting you off today? Your feedback genuinely helps us improve.",
        6)
    add_objection(client_id,
        "I've heard solar companies go out of business and warranties become worthless",
        "That's a real concern in this industry. Being a CEC Approved Retailer means if we ever closed, the CEC has a fund to honour warranties. On top of that, panel and inverter warranties are held directly with the manufacturers — completely independent of us.",
        7)
    add_objection(client_id,
        "My neighbour had a bad experience with solar",
        "Sorry to hear that — unfortunately there are still some fly-by-night installers around. We're a CEC Approved Retailer held to the highest standard in the industry. I'd be happy to give you a free second opinion on any work you're concerned about.",
        8)

    print(f"[KB] Demo company seeded: {client_id}")


def init_demo_client():
    """Seed demo company data if it doesn't already exist.

    Safe to call on every startup — checks before inserting.
    """
    init_kb_tables()
    existing = fetch_one(
        "SELECT id FROM company_profiles WHERE client_id = ?",
        ("suntech_solar_perth",)
    )
    if not existing:
        seed_demo_company("suntech_solar_perth")
        print("[KB] Demo client initialised.")
    else:
        logger.debug("[KB] Demo client already present — skipping seed.")
