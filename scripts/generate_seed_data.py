"""
Bertie Sweet Online Shop - synthetic data generator
----------------------------------------------------
Generates sql/02_seed_data.sql with realistic, reproducible sample data:
  * 2 full trading years (2024-2025) with seasonality (Easter, Halloween, Christmas)
  * customer segments (one-off, occasional, loyal, super-fan) to model repeat purchasing
  * time-boxed promotional offers applied to order lines
  * a 5% price rise on 1 Jan 2025 (order lines keep the price paid at time of sale)

Usage (from the repo root):
    python scripts/generate_seed_data.py
"""
import random
import string
from datetime import date, timedelta
from pathlib import Path

random.seed(42)  # reproducible output

OUT = Path(__file__).resolve().parent.parent / "sql" / "02_seed_data.sql"
START, END = date(2024, 1, 1), date(2025, 12, 31)

# ---------------------------------------------------------------- reference data
REGIONS = ["London", "South East", "Midlands", "North West", "Yorkshire", "Scotland"]
REGION_CITIES = {
    "London": [("London", "E1"), ("London", "N7"), ("London", "SW11"), ("London", "SE15")],
    "South East": [("Brighton", "BN1"), ("Reading", "RG1"), ("Oxford", "OX4"), ("Guildford", "GU1")],
    "Midlands": [("Birmingham", "B15"), ("Leicester", "LE1"), ("Nottingham", "NG7"), ("Coventry", "CV1")],
    "North West": [("Manchester", "M14"), ("Liverpool", "L8"), ("Preston", "PR1"), ("Chester", "CH1")],
    "Yorkshire": [("Leeds", "LS6"), ("Sheffield", "S10"), ("York", "YO1"), ("Bradford", "BD7")],
    "Scotland": [("Glasgow", "G12"), ("Edinburgh", "EH3"), ("Aberdeen", "AB10"), ("Dundee", "DD1")],
}
# share of customers per region
REGION_WEIGHTS = [0.24, 0.20, 0.17, 0.15, 0.13, 0.11]

CATEGORIES = ["Chocolate", "Fudge & Toffee", "Boiled Sweets", "Gummies & Jellies",
              "Liquorice", "Sherbet & Fizz", "Sugar-Free", "Seasonal Specials"]

# (name, category, grams, price, popularity weight)
SWEETS = [
    ("Milk Chocolate Buttons", "Chocolate", 150, 3.20, 9),
    ("Dark Chocolate Gingers", "Chocolate", 200, 4.50, 5),
    ("White Chocolate Mice", "Chocolate", 150, 2.95, 6),
    ("Chocolate Brazil Nuts", "Chocolate", 200, 5.25, 4),
    ("Salted Caramel Truffles", "Chocolate", 180, 6.50, 7),
    ("Mint Chocolate Crisps", "Chocolate", 150, 3.75, 5),
    ("Clotted Cream Fudge", "Fudge & Toffee", 200, 4.25, 7),
    ("Rum & Raisin Fudge", "Fudge & Toffee", 200, 4.25, 3),
    ("Treacle Toffee Slab", "Fudge & Toffee", 250, 3.80, 4),
    ("Butterscotch Bites", "Fudge & Toffee", 200, 3.10, 4),
    ("Peanut Brittle", "Fudge & Toffee", 200, 3.95, 3),
    ("Rhubarb & Custards", "Boiled Sweets", 200, 2.60, 8),
    ("Pear Drops", "Boiled Sweets", 200, 2.60, 5),
    ("Sherbet Lemons", "Boiled Sweets", 200, 2.60, 7),
    ("Cola Cubes", "Boiled Sweets", 200, 2.60, 6),
    ("Aniseed Balls", "Boiled Sweets", 200, 2.40, 2),
    ("Kola Kubes Sour", "Boiled Sweets", 200, 2.75, 3),
    ("Fizzy Cola Bottles", "Gummies & Jellies", 200, 2.85, 9),
    ("Sour Snakes", "Gummies & Jellies", 200, 2.85, 6),
    ("Fruit Jelly Babies", "Gummies & Jellies", 200, 2.70, 7),
    ("Foam Bananas", "Gummies & Jellies", 150, 2.40, 4),
    ("Strawberry Laces", "Gummies & Jellies", 150, 2.50, 6),
    ("Vegan Gummy Bears", "Gummies & Jellies", 200, 3.30, 5),
    ("Liquorice Allsorts", "Liquorice", 200, 2.90, 5),
    ("Salted Liquorice Coins", "Liquorice", 150, 3.40, 2),
    ("Red Liquorice Twists", "Liquorice", 200, 2.80, 3),
    ("Sherbet Fountains", "Sherbet & Fizz", 50, 0.95, 6),
    ("Flying Saucers", "Sherbet & Fizz", 50, 1.20, 5),
    ("Fizz Whizz Popping Candy", "Sherbet & Fizz", 50, 1.10, 4),
    ("Dip Dab Sherbet", "Sherbet & Fizz", 50, 1.00, 3),
    ("Sugar-Free Mint Imperials", "Sugar-Free", 150, 2.95, 3),
    ("Sugar-Free Fruit Drops", "Sugar-Free", 150, 3.10, 3),
    ("Sugar-Free Choc Coins", "Sugar-Free", 120, 3.95, 2),
    ("Christmas Pudding Truffles", "Seasonal Specials", 180, 6.95, 4),
    ("Easter Mini Eggs Mix", "Seasonal Specials", 200, 4.50, 4),
    ("Halloween Pick & Mix", "Seasonal Specials", 300, 4.95, 4),
    ("Valentine Love Hearts Tub", "Seasonal Specials", 150, 3.50, 3),
    ("Gingerbread Fudge", "Seasonal Specials", 200, 4.75, 3),
]

MULTI_PACKS = [  # (name, description, price, [(sweet_index, qty)])
    ("Retro Classics Box", "Six bags of old-school favourites", 13.50, [(11, 2), (13, 2), (14, 2)]),
    ("Chocoholic Hamper", "Four premium chocolate treats", 17.95, [(0, 1), (1, 1), (4, 1), (5, 1)]),
    ("Fizz Frenzy Pack", "Sherbet and fizzy sweets bundle", 6.50, [(26, 2), (27, 2), (28, 2)]),
    ("Fudge Lovers Trio", "Three slabs of handmade fudge", 11.50, [(6, 1), (7, 1), (8, 1)]),
    ("Party Pick & Mix", "Gummies for parties - serves 10", 14.95, [(17, 2), (18, 2), (19, 2)]),
    ("Sugar-Free Selection", "Guilt-free trio", 9.20, [(30, 1), (31, 1), (32, 1)]),
    ("Liquorice Lovers", "Every kind of liquorice", 8.40, [(23, 1), (24, 1), (25, 1)]),
    ("Christmas Stocking", "Festive favourites", 15.95, [(33, 1), (37, 1), (0, 1), (11, 1)]),
    ("Easter Basket", "Spring chocolate selection", 12.50, [(34, 2), (2, 1)]),
    ("Halloween Trick Box", "Spooky sweets bundle", 10.95, [(35, 1), (18, 1), (21, 1)]),
]

OFFERS = [  # (name, discount %, [(month_start, day_start, month_end, day_end)], categories)
    ("Valentine Sweetheart", 15, (2, 1, 2, 14), ["Chocolate", "Seasonal Specials"]),
    ("Easter Egg-stravaganza", 15, (3, 15, 4, 10), ["Chocolate", "Seasonal Specials"]),
    ("Summer Fizz", 10, (6, 15, 8, 31), ["Sherbet & Fizz", "Gummies & Jellies"]),
    ("Back to School", 10, (9, 1, 9, 21), ["Boiled Sweets", "Sugar-Free"]),
    ("Halloween Treats", 20, (10, 15, 10, 31), ["Gummies & Jellies", "Seasonal Specials"]),
    ("Christmas Cracker", 25, (12, 1, 12, 24), ["Chocolate", "Fudge & Toffee", "Seasonal Specials"]),
]

# Monthly demand multipliers (Jan..Dec)
SEASONALITY = [0.75, 1.05, 1.0, 1.25, 0.85, 0.85, 0.95, 0.95, 0.9, 1.35, 1.25, 1.9]
# Category boosts by month
CATEGORY_SEASON = {
    "Chocolate": {2: 1.6, 4: 1.5, 12: 1.8},
    "Sherbet & Fizz": {6: 1.6, 7: 1.8, 8: 1.7},
    "Gummies & Jellies": {7: 1.3, 10: 1.6},
    "Fudge & Toffee": {11: 1.4, 12: 1.6},
}

FIRST = ["Olivia", "Amelia", "Isla", "Ava", "Mia", "Ivy", "Lily", "Isabella", "Sophia", "Grace",
         "Noah", "Oliver", "George", "Arthur", "Muhammad", "Leo", "Harry", "Oscar", "Archie", "Henry",
         "Aisha", "Priya", "Zara", "Fatima", "Chloe", "Ella", "Ruby", "Freya", "Jack", "Theo",
         "Charlie", "Alfie", "Finley", "Ibrahim", "Yusuf", "Ethan", "Daniel", "Emily", "Hannah", "Sofia"]
LAST = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Patel", "Robinson",
        "Wright", "Thompson", "Evans", "Walker", "White", "Roberts", "Green", "Hall", "Wood", "Jackson",
        "Khan", "Hussain", "Ali", "Clarke", "Hughes", "Edwards", "Lewis", "Murphy", "Campbell", "Stewart"]
STREETS = ["High Street", "Station Road", "Church Lane", "Victoria Road", "Park Avenue", "Mill Lane",
           "Queens Road", "Kings Road", "Green Lane", "Manor Way", "Albert Street", "The Crescent"]

# Customer segments: (share, min orders, max orders)
SEGMENTS = [("one_off", 0.38, 1, 1), ("occasional", 0.34, 2, 4),
            ("loyal", 0.22, 5, 12), ("super_fan", 0.06, 13, 30)]

N_CUSTOMERS = 1200


# ---------------------------------------------------------------- helpers
def q(v):
    """SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, date):
        return f"'{v.isoformat()}'"
    return "'" + str(v).replace("'", "''") + "'"


def insert(table, cols, rows, batch=500):
    out = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        values = ",\n  ".join("(" + ", ".join(q(v) for v in r) + ")" for r in chunk)
        out.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n  {values};\n")
    return "\n".join(out)


def rand_date(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))


def phone():
    return "0" + "".join(random.choices(string.digits, k=10))


def full_postcode(district):
    return f"{district} {random.randint(1, 9)}{random.choice('ABDEFGHJLNPQRSTUWXYZ')}{random.choice('ABDEFGHJLNPQRSTUWXYZ')}"


def price_on(base_price, d):
    """Current catalogue price applies from 2025; 2024 prices were ~5% lower."""
    return round(base_price / 1.05, 2) if d.year == 2024 else base_price


# ---------------------------------------------------------------- build
sql = ["-- =====================================================================",
       "--  Bertie Sweet Online Shop  |  02_seed_data.sql",
       "--  AUTO-GENERATED by scripts/generate_seed_data.py (random.seed(42))",
       "-- =====================================================================",
       "SET search_path TO bertie;", "BEGIN;", ""]

# Regions / warehouses / DCs
sql.append(insert("region", ["region_id", "region_name"], [(i + 1, r) for i, r in enumerate(REGIONS)]))
wh_rows, dc_rows, region_dcs = [], [], {}
dc_id = 0
for i, r in enumerate(REGIONS, start=1):
    city, district = REGION_CITIES[r][0]
    wh_rows.append((i, i, f"Bertie {r} Warehouse", f"Unit {random.randint(1, 40)}, {random.choice(STREETS)}, {city}",
                    phone(), full_postcode(district)))
    region_dcs[i] = []
    for city, district in REGION_CITIES[r][1:3]:
        dc_id += 1
        region_dcs[i].append(dc_id)
        dc_rows.append((dc_id, i, f"{city} Distribution Centre",
                        f"{random.randint(1, 200)} {random.choice(STREETS)}, {city}", phone(), full_postcode(district)))
sql.append(insert("warehouse", ["warehouse_id", "region_id", "warehouse_name", "warehouse_address",
                                "warehouse_telephone", "warehouse_postcode"], wh_rows))
sql.append(insert("distribution_centre", ["dc_id", "warehouse_id", "dc_name", "dc_address", "dc_telephone",
                                          "dc_postcode"], dc_rows))

# Catalogue
sql.append(insert("sweet_category", ["category_id", "category_name"],
                  [(i + 1, c) for i, c in enumerate(CATEGORIES)]))
cat_id = {c: i + 1 for i, c in enumerate(CATEGORIES)}
sweet_rows = []
for i, (name, cat, g, price, _) in enumerate(SWEETS):
    sweet_rows.append((f"SW{i + 1:03d}", name, f"{name} - {g}g bag", g, price, cat_id[cat], True))
sql.append(insert("sweet", ["sweet_code", "sweet_name", "sweet_description", "size_grams", "unit_price",
                            "category_id", "is_active"], sweet_rows))
code = lambda idx: f"SW{idx + 1:03d}"

sql.append(insert("multi_pack", ["multi_pack_id", "multi_pack_name", "multi_pack_description", "multi_pack_price"],
                  [(i + 1, n, d, p) for i, (n, d, p, _) in enumerate(MULTI_PACKS)]))
sql.append(insert("multi_pack_item", ["multi_pack_id", "sweet_code", "quantity"],
                  [(i + 1, code(s), qn) for i, mp in enumerate(MULTI_PACKS) for s, qn in mp[3]]))

# Offers
sql.append(insert("offer", ["offer_id", "offer_name", "discount_pct"],
                  [(i + 1, n, d) for i, (n, d, _, _) in enumerate(OFFERS)]))
sweet_offer_rows, offer_lookup = [], []  # offer_lookup: (sweet_code, start, end, pct)
for oi, (n, pct, (m1, d1, m2, d2), cats) in enumerate(OFFERS, start=1):
    eligible = [i for i, s in enumerate(SWEETS) if s[1] in cats]
    for yr in (2024, 2025):
        chosen = random.sample(eligible, k=max(2, int(len(eligible) * 0.6)))
        for s in chosen:
            st, en = date(yr, m1, d1), date(yr, m2, d2)
            sweet_offer_rows.append((code(s), oi, st, en))
            offer_lookup.append((s, st, en, pct))
sql.append(insert("sweet_offer", ["sweet_code", "offer_id", "offer_start_date", "offer_end_date"], sweet_offer_rows))


def discount_for(s_idx, d):
    best = 0
    for s, st, en, pct in offer_lookup:
        if s == s_idx and st <= d <= en:
            best = max(best, pct)
    return best


# Stock
stock_rows = []
for dc in range(1, dc_id + 1):
    for i in range(len(SWEETS)):
        stock_rows.append((dc, code(i), random.randint(0, 600), random.choice([40, 50, 75, 100])))
sql.append(insert("stock", ["dc_id", "sweet_code", "quantity_on_hand", "reorder_level"], stock_rows))

# Customers, addresses, payment methods
cust_rows, addr_rows, pay_rows, customers = [], [], [], []
used_usernames = set()
addr_id = pay_id = 0
for cid in range(1, N_CUSTOMERS + 1):
    fn, ln = random.choice(FIRST), random.choice(LAST)
    base = f"{fn.lower()}.{ln.lower()}"
    uname = base
    while uname in used_usernames:
        uname = f"{base}{random.randint(1, 999)}"
    used_usernames.add(uname)
    reg = rand_date(date(2023, 6, 1), date(2025, 9, 30))
    pw = "$2b$12$" + "".join(random.choices(string.ascii_letters + string.digits + "./", k=53))
    cust_rows.append((cid, uname, f"{fn} {ln}", f"{uname}@example.com", pw, reg))

    region = random.choices(range(1, 7), weights=REGION_WEIGHTS)[0]
    city, district = random.choice(REGION_CITIES[REGIONS[region - 1]])
    addr_id += 1
    addr_rows.append((addr_id, cid, f"{random.randint(1, 250)} {random.choice(STREETS)}", city,
                      full_postcode(district), region, True))
    my_addrs = [(addr_id, region)]
    if random.random() < 0.15:  # some customers have a second (gift / work) address
        r2 = random.randint(1, 6)
        c2, d2 = random.choice(REGION_CITIES[REGIONS[r2 - 1]])
        addr_id += 1
        addr_rows.append((addr_id, cid, f"{random.randint(1, 250)} {random.choice(STREETS)}", c2,
                          full_postcode(d2), r2, False))
        my_addrs.append((addr_id, r2))

    pay_id += 1
    ctype = random.choices(["Visa", "Mastercard", "Amex", "PayPal"], weights=[50, 30, 8, 12])[0]
    last4 = None if ctype == "PayPal" else "".join(random.choices(string.digits, k=4))
    pay_rows.append((pay_id, cid, ctype, last4, "tok_" + "".join(random.choices(string.hexdigits.lower(), k=24)),
                     f"{ctype} ending {last4}" if last4 else "PayPal account"))

    seg = random.choices(SEGMENTS, weights=[s[1] for s in SEGMENTS])[0]
    # each customer has 2-3 favourite categories -> drives repeat purchasing of the same products
    favs = random.sample(CATEGORIES, k=random.randint(2, 3))
    customers.append(dict(id=cid, reg=reg, addrs=my_addrs, pay=pay_id, seg=seg, favs=favs))

sql.append(insert("customer", ["customer_id", "username", "full_name", "email", "password_hash", "registered_on"],
                  cust_rows))
sql.append(insert("delivery_address", ["address_id", "customer_id", "address_line", "city", "postcode",
                                       "region_id", "is_default"], addr_rows))
sql.append(insert("payment_method", ["payment_method_id", "customer_id", "card_type", "card_last4",
                                     "payment_token", "payment_description"], pay_rows))

# Orders
all_days = [START + timedelta(days=i) for i in range((END - START).days + 1)]


def day_weight(d):
    growth = 1 + 0.25 * ((d - START).days / (END - START).days)  # ~25% growth across the period
    weekend = 1.15 if d.weekday() >= 5 else 1.0
    return SEASONALITY[d.month - 1] * growth * weekend


# Seasonal lines only sell properly in their own season
SEASONAL_MONTHS = {"Christmas Pudding Truffles": {11: 3, 12: 6}, "Gingerbread Fudge": {11: 3, 12: 5},
                   "Easter Mini Eggs Mix": {3: 4, 4: 6}, "Halloween Pick & Mix": {10: 7, 11: 1},
                   "Valentine Love Hearts Tub": {2: 7}}


def pick_sweet(d, favs):
    weights = []
    for i, (name, cat, _, _, pop) in enumerate(SWEETS):
        if name in SEASONAL_MONTHS:
            w = pop * SEASONAL_MONTHS[name].get(d.month, 0.08)
        else:
            w = pop * CATEGORY_SEASON.get(cat, {}).get(d.month, 1.0)
        if cat in favs:
            w *= 3
        if discount_for(i, d):  # promotions lift demand
            w *= 2.2
        weights.append(w)
    return random.choices(range(len(SWEETS)), weights=weights)[0]


basket_rows, basket_item_rows, order_rows, item_rows = [], [], [], []
order_id = basket_id = basket_item_id = item_id = 0
for c in customers:
    first_possible = max(c["reg"], START)
    if first_possible > END:
        continue
    window = [d for d in all_days if d >= first_possible]
    n = random.randint(c["seg"][2], c["seg"][3])
    # customers who join later have less time to re-order -> scale by their active window
    n = max(1, round(n * len(window) / len(all_days)))
    dates = sorted(random.choices(window, weights=[day_weight(d) for d in window], k=n))
    for od in dates:
        addr, region = random.choice(c["addrs"]) if random.random() < 0.2 else c["addrs"][0]
        dc = random.choice(region_dcs[region])
        basket_id += 1
        basket_rows.append((basket_id, c["id"], f"{od.isoformat()} {random.randint(7, 22):02d}:{random.randint(0, 59):02d}:00",
                            "checked_out"))
        order_id += 1
        subtotal = 0.0
        lines = {}
        for _ in range(random.choices([1, 2, 3, 4, 5, 6], weights=[22, 28, 22, 14, 9, 5])[0]):
            if random.random() < 0.12:  # multi-pack line
                mp = random.randint(1, len(MULTI_PACKS))
                if od.month == 12 and random.random() < 0.5:
                    mp = 8
                key = ("mp", mp)
                if key in lines:
                    continue
                qty = random.choices([1, 2], weights=[85, 15])[0]
                up = price_on(MULTI_PACKS[mp - 1][2], od)
                lines[key] = (None, mp, qty, up, 0)
            else:
                s = pick_sweet(od, c["favs"])
                key = ("sw", s)
                if key in lines:
                    continue
                qty = random.choices([1, 2, 3, 4], weights=[55, 28, 11, 6])[0]
                up = price_on(SWEETS[s][3], od)
                lines[key] = (code(s), None, qty, up, discount_for(s, od))
        for sc, mp, qty, up, disc in lines.values():
            item_id += 1
            basket_item_id += 1
            item_rows.append((item_id, order_id, sc, mp, qty, up, disc))
            basket_item_rows.append((basket_item_id, basket_id, sc, mp, qty))
            subtotal += qty * up * (1 - disc / 100)
        charge = 0.0 if subtotal >= 25 else 3.95
        status = random.choices(["delivered", "cancelled"], weights=[97, 3])[0]
        dd = od + timedelta(days=random.randint(1, 4)) if status == "delivered" else None
        order_rows.append((order_id, c["id"], basket_id, dc, addr, c["pay"], od, dd, charge, status))

    # abandoned baskets (not converted to orders)
    for _ in range(random.choices([0, 1, 2], weights=[60, 30, 10])[0]):
        bd = rand_date(first_possible, END)
        basket_id += 1
        basket_rows.append((basket_id, c["id"], f"{bd.isoformat()} {random.randint(7, 23):02d}:{random.randint(0, 59):02d}:00",
                            "abandoned"))
        for s in random.sample(range(len(SWEETS)), k=random.randint(1, 3)):
            basket_item_id += 1
            basket_item_rows.append((basket_item_id, basket_id, code(s), None, random.randint(1, 3)))

sql.append(insert("shopping_basket", ["basket_id", "customer_id", "created_at", "status"], basket_rows))
sql.append(insert("basket_item", ["basket_item_id", "basket_id", "sweet_code", "multi_pack_id", "quantity"],
                  basket_item_rows))
sql.append(insert("customer_order", ["order_id", "customer_id", "basket_id", "dc_id", "address_id",
                                     "payment_method_id", "order_date", "delivery_date", "delivery_charge",
                                     "order_status"], order_rows))
sql.append(insert("order_item", ["order_item_id", "order_id", "sweet_code", "multi_pack_id", "quantity",
                                 "unit_price", "discount_pct"], item_rows))

# Shopping lists
sl_rows, sli_rows, sl_id, sli_id = [], [], 0, 0
for c in random.sample(customers, k=220):
    sl_id += 1
    cd = rand_date(max(c["reg"], START), END)
    sl_rows.append((sl_id, c["id"], random.choice(["Party", "Birthday", "Christmas", "Weekly treats", "Wishlist",
                                                   "Office snacks"]), cd, cd + timedelta(days=random.choice([30, 60, 90]))))
    for s in random.sample(range(len(SWEETS)), k=random.randint(2, 6)):
        sli_id += 1
        sli_rows.append((sli_id, sl_id, code(s), None, random.randint(1, 4)))
    if random.random() < 0.3:
        sli_id += 1
        sli_rows.append((sli_id, sl_id, None, random.randint(1, len(MULTI_PACKS)), 1))
sql.append(insert("shopping_list", ["shopping_list_id", "customer_id", "list_name", "created_on", "expires_on"],
                  sl_rows))
sql.append(insert("shopping_list_item", ["list_item_id", "shopping_list_id", "sweet_code", "multi_pack_id",
                                         "quantity"], sli_rows))

# Special (bulk) orders
so_rows, soi_rows, soi_id = [], [], 0
for so_id in range(1, 46):
    c = random.choice(customers)
    od = rand_date(max(c["reg"], START), END - timedelta(days=30))
    dc = random.choice(region_dcs[c["addrs"][0][1]])
    so_rows.append((so_id, c["id"], dc, od, od + timedelta(days=random.randint(7, 28))))
    for s in random.sample(range(len(SWEETS)), k=random.randint(1, 4)):
        soi_id += 1
        soi_rows.append((soi_id, so_id, code(s), None, random.choice([24, 36, 48, 60, 100]),
                         round(price_on(SWEETS[s][3], od) * 0.85, 2)))  # 15% bulk price
sql.append(insert("special_order", ["special_order_id", "customer_id", "dc_id", "order_date", "delivery_date"],
                  so_rows))
sql.append(insert("special_order_item", ["special_order_item_id", "special_order_id", "sweet_code",
                                         "multi_pack_id", "quantity", "unit_price"], soi_rows))

# Standing (recurring) orders - mostly loyal / super-fan customers
st_rows, sti_rows, sti_id = [], [], 0
loyal = [c for c in customers if c["seg"][0] in ("loyal", "super_fan")]
for st_id, c in enumerate(random.sample(loyal, k=min(70, len(loyal))), start=1):
    sd = rand_date(max(c["reg"], START), END - timedelta(days=60))
    revised = sd + timedelta(days=random.randint(30, 200)) if random.random() < 0.35 else None
    if revised and revised > END:
        revised = None
    st_rows.append((st_id, c["id"], random.choice(region_dcs[c["addrs"][0][1]]), sd,
                    random.choices(["weekly", "fortnightly", "monthly"], weights=[20, 30, 50])[0],
                    random.choice(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]),
                    revised, random.random() > 0.15))
    for s in random.sample(range(len(SWEETS)), k=random.randint(1, 3)):
        sti_id += 1
        sti_rows.append((sti_id, st_id, code(s), None, random.randint(1, 3)))
sql.append(insert("standing_order", ["standing_order_id", "customer_id", "dc_id", "start_date", "frequency",
                                     "delivery_day", "revised_date", "is_active"], st_rows))
sql.append(insert("standing_order_item", ["standing_order_item_id", "standing_order_id", "sweet_code",
                                          "multi_pack_id", "quantity"], sti_rows))

# Re-sync sequences after explicit IDs
seqs = [("region", "region_id"), ("warehouse", "warehouse_id"), ("distribution_centre", "dc_id"),
        ("sweet_category", "category_id"), ("multi_pack", "multi_pack_id"), ("offer", "offer_id"),
        ("customer", "customer_id"), ("delivery_address", "address_id"), ("payment_method", "payment_method_id"),
        ("shopping_list", "shopping_list_id"), ("shopping_list_item", "list_item_id"),
        ("shopping_basket", "basket_id"), ("basket_item", "basket_item_id"), ("customer_order", "order_id"),
        ("order_item", "order_item_id"), ("special_order", "special_order_id"),
        ("special_order_item", "special_order_item_id"), ("standing_order", "standing_order_id"),
        ("standing_order_item", "standing_order_item_id")]
sql.append("-- keep SERIAL sequences in step with the explicit IDs above")
for t, col in seqs:
    sql.append(f"SELECT setval(pg_get_serial_sequence('bertie.{t}', '{col}'), (SELECT MAX({col}) FROM {t}));")
sql.append("\nCOMMIT;\n")

OUT.write_text("\n".join(sql), encoding="utf-8")
print(f"Wrote {OUT}  |  customers={N_CUSTOMERS} orders={order_id} order_lines={item_id} baskets={basket_id}")
