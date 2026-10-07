"""
Builds tableau/bertie_sweets_dashboard.twb from the CSV extracts in tableau/data/.

Usage (from the repo root):
    python scripts/build_tableau_workbook.py [absolute/path/to/tableau/data]

Open the .twb in Tableau Desktop / Public, then File > Export Packaged Workbook
(.twbx) to bundle the data for sharing.
"""
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr, escape

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tableau" / "data"
DATA_DIR_IN_TWB = sys.argv[1] if len(sys.argv) > 1 else str(DATA)
OUT = ROOT / "tableau" / "bertie_sweets_dashboard.twb"

A = quoteattr
GBP = 'c"£"#,##0;-"£"#,##0'
GBP2 = 'c"£"#,##0.00;-"£"#,##0.00'

# ------------------------------------------------------------------ data sources
SOURCES = {
    "order_line_sales": "Order Line Sales",
    "order_summary": "Order Summary",
    "customer_summary": "Customer Summary",
    "monthly_category_revenue": "Monthly Category Revenue",
    "product_performance": "Product Performance",
    "cohort_retention": "Cohort Retention",
}
DATE_COLS = {"order_date", "order_month", "registered_on", "first_order_date", "last_order_date", "cohort_month"}
DIM_INTS = {"order_item_id", "order_id", "customer_id", "months_since_first", "overall_rank",
            "rank_in_category", "customer_order_seq"}
FORMATS = {"net_revenue": GBP, "gross_revenue": GBP, "revenue": GBP, "order_total": GBP,
           "lifetime_value": GBP, "avg_order_value": GBP2, "discount_amount": GBP}

# calculated fields per source: (id, caption, formula, datatype, role, type, format)
CALCS = {
    "order_summary": [
        ("Calc_AOV", "Avg Order Value", "SUM([order_total]) / COUNTD([order_id])", "real", "measure",
         "quantitative", GBP2),
        ("Calc_RepeatPct", "Repeat Order %", 'SUM(IIF([new_vs_repeat] = "Repeat", 1, 0)) / COUNT([order_id])',
         "real", "measure", "quantitative", "p0.0%"),
    ],
    "cohort_retention": [
        ("Calc_Retention", "Retention %", "SUM([active_customers]) / SUM([cohort_customers])", "real",
         "measure", "quantitative", "p0%"),
    ],
    "product_performance": [
        ("Calc_RepeatBuyer", "Repeat Buyer Rate", "SUM([repeat_buyers]) / SUM([buyers])", "real", "measure",
         "quantitative", "p0.0%"),
        ("Calc_Top10", "Top 10 Product", "[overall_rank] <= 10", "boolean", "dimension", "nominal", None),
    ],
    "customer_summary": [
        ("Calc_RevShare", "% of Revenue", "SUM([lifetime_value]) / MIN({FIXED : SUM([lifetime_value])})", "real",
         "measure", "quantitative", "p0%"),
    ],
}

meta = {}  # source -> {col: (datatype, role, type)}


def col_meta(name, dtype):
    if name in DATE_COLS:
        return "date", "dimension", "ordinal"
    if dtype.startswith("int"):
        return ("integer", "dimension", "ordinal") if name in DIM_INTS else ("integer", "measure", "quantitative")
    if dtype.startswith("float"):
        return "real", "measure", "quantitative"
    return "string", "dimension", "nominal"


def ds_name(src):
    return f"federated.{src}"


def datasource_xml(src):
    df = pd.read_csv(DATA / f"{src}.csv", nrows=50)
    cols = {}
    rel_cols, ds_cols = [], []
    for i, (c, t) in enumerate(df.dtypes.astype(str).items()):
        dt, role, typ = col_meta(c, t)
        cols[c] = (dt, role, typ)
        rel_cols.append(f"            <column datatype={A(dt)} name={A(c)} ordinal={A(str(i))} />")
        fmt = f" default-format={A(FORMATS[c])}" if c in FORMATS else ""
        cap = c.replace("_", " ").title()
        ds_cols.append(f"    <column caption={A(cap)} datatype={A(dt)}{fmt} name={A('[' + c + ']')} "
                       f"role={A(role)} type={A(typ)} />")
    for cid, cap, formula, dt, role, typ, fmt in CALCS.get(src, []):
        cols[cid] = (dt, role, typ)
        f = f" default-format={A(fmt)}" if fmt else ""
        ds_cols.append(f"    <column caption={A(cap)} datatype={A(dt)}{f} name={A('[' + cid + ']')} role={A(role)} "
                       f"type={A(typ)}>\n      <calculation class='tableau' formula={A(formula)} />\n    </column>")
    meta[src] = cols
    return f"""  <datasource caption={A(SOURCES[src])} inline='true' name={A(ds_name(src))} version='18.1'>
    <connection class='federated'>
      <named-connections>
        <named-connection caption={A(src)} name={A('textscan.' + src)}>
          <connection class='textscan' directory={A(DATA_DIR_IN_TWB)} filename={A(src + '.csv')} password='' server='' />
        </named-connection>
      </named-connections>
      <relation connection={A('textscan.' + src)} name={A(src + '.csv')} table={A('[' + src + '#csv]')} type='table'>
        <columns character-set='UTF-8' header='yes' locale='en_GB' separator=','>
{chr(10).join(rel_cols)}
        </columns>
      </relation>
    </connection>
    <aliases enabled='yes' />
{chr(10).join(ds_cols)}
    <layout dim-ordering='alphabetic' dim-percentage='0.5' measure-ordering='alphabetic' measure-percentage='0.4' show-structure='true' />
  </datasource>"""


# ------------------------------------------------------------------ field instances
DERIV = {"none": "None", "sum": "Sum", "avg": "Avg", "cnt": "Count", "ctd": "CountD",
         "yr": "Year", "tmn": "Month-Trunc", "tqr": "Quarter-Trunc", "usr": "User"}


def inst(prefix, field, kind):
    """kind: nk / ok / qk"""
    return (prefix, field, kind)


def inst_name(i):
    p, f, k = i
    return f"[{p}:{f}:{k}]"


def ref(src, i):
    return f"[{ds_name(src)}].{inst_name(i)}"


def deps_xml(src, instances):
    cols = meta[src]
    fields = sorted({i[1] for i in instances})
    out = []
    for f in fields:
        dt, role, typ = cols[f]
        calc = next((c for c in CALCS.get(src, []) if c[0] == f), None)
        if calc:
            fmt = f" default-format={A(calc[6])}" if calc[6] else ""
            out.append(f"            <column caption={A(calc[1])} datatype={A(dt)}{fmt} name={A('[' + f + ']')} "
                       f"role={A(role)} type={A(typ)}>\n              <calculation class='tableau' "
                       f"formula={A(calc[2])} />\n            </column>")
        else:
            fmt = f" default-format={A(FORMATS[f])}" if f in FORMATS else ""
            out.append(f"            <column datatype={A(dt)}{fmt} name={A('[' + f + ']')} role={A(role)} type={A(typ)} />")
    for i in sorted(set(instances)):
        p, f, k = i
        typ = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}[k]
        out.append(f"            <column-instance column={A('[' + f + ']')} derivation={A(DERIV[p])} "
                   f"name={A(inst_name(i))} pivot='key' type={A(typ)} />")
    return "\n".join(out)


def shelf(src, items):
    if not items:
        return ""
    parts = [ref(src, i) for i in items]
    return parts[0] if len(parts) == 1 else "(" + " / ".join(parts) + ")"


def worksheet(name, src, rows=(), cols=(), mark="Automatic", color=None, size=None, text=None,
              filters=(), sort=None, style="", labels=False, title=None, detail=None):
    instances = list(rows) + list(cols) + [x for x in (color, size, text, detail) if x] + [f[0] for f in filters]
    if sort:
        instances += [sort[0], sort[1]]
    filt_xml = ""
    slices = ""
    for fi, member in filters:
        members = member if isinstance(member, (list, tuple)) else [member]
        attrs = "user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'"
        if len(members) == 1:
            gf = (f"            <groupfilter function='member' level={A(inst_name(fi))} member={A(members[0])} "
                  f"{attrs} />")
        else:
            inner = "\n".join(f"              <groupfilter function='member' level={A(inst_name(fi))} member={A(m)} />"
                               for m in members)
            gf = f"            <groupfilter function='union' {attrs}>\n{inner}\n            </groupfilter>"
        filt_xml += f"\n          <filter class='categorical' column={A(ref(src, fi))}>\n{gf}\n          </filter>"
        slices += f"\n            <column>{ref(src, fi)}</column>"
    if slices:
        slices = f"\n          <slices>{slices}\n          </slices>"
    sort_xml = ""
    if sort:
        sort_xml = (f"\n          <sort class='computed' column={A(ref(src, sort[0]))} direction={A(sort[2])} "
                    f"using={A(ref(src, sort[1]))} />")
    enc = ""
    for tag, x in (("color", color), ("size", size), ("lod", detail), ("text", text)):
        if x:
            enc += f"\n              <{tag} column={A(ref(src, x))} />"
    enc = f"\n            <encodings>{enc}\n            </encodings>" if enc else ""
    title_xml = ""
    if title:
        title_xml = (f"\n      <layout-options>\n        <title>\n          <formatted-text>\n"
                     f"            <run>{escape(title)}</run>\n          </formatted-text>\n        </title>\n"
                     f"      </layout-options>")
    return f"""    <worksheet name={A(name)}>{title_xml}
      <table>
        <view>
          <datasources>
            <datasource caption={A(SOURCES[src])} name={A(ds_name(src))} />
          </datasources>
          <datasource-dependencies datasource={A(ds_name(src))}>
{deps_xml(src, instances)}
          </datasource-dependencies>{filt_xml}{sort_xml}{slices}
          <aggregation value='true' />
        </view>
        <style>{style}
        </style>
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class={A(mark)} />{enc}{LABEL_STYLE if labels else ""}
          </pane>
        </panes>
        <rows>{escape(shelf(src, rows))}</rows>
        <cols>{escape(shelf(src, cols))}</cols>
      </table>
    </worksheet>"""


def uuid_for(name):
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "bertie." + name)).upper()


LABEL_STYLE = """
            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
              </style-rule>
            </style>"""

KPI_STYLE = """
          <style-rule element='cell'>
            <format attr='font-size' value='26' />
            <format attr='font-weight' value='bold' />
            <format attr='color' value='#4e2a84' />
            <format attr='text-align' value='center' />
          </style-rule>"""

# ------------------------------------------------------------------ build
datasources = "\n".join(datasource_xml(s) for s in SOURCES)

S = []
# KPI tiles
S.append(worksheet("KPI Revenue", "order_summary", mark="Text", title="Total Revenue", text=inst("sum", "order_total", "qk"),
                   style=KPI_STYLE))
S.append(worksheet("KPI Orders", "order_summary", mark="Text", title="Orders", text=inst("ctd", "order_id", "qk"),
                   style=KPI_STYLE))
S.append(worksheet("KPI Avg Order Value", "order_summary", mark="Text", title="Avg Order Value", text=inst("usr", "Calc_AOV", "qk"),
                   style=KPI_STYLE))
S.append(worksheet("KPI Repeat Order %", "order_summary", mark="Text", title="Repeat Order Rate", text=inst("usr", "Calc_RepeatPct", "qk"),
                   style=KPI_STYLE))
# Revenue trend by category (stacked area)
S.append(worksheet("Revenue Trend by Category", "monthly_category_revenue",
                   cols=[inst("tmn", "order_month", "qk")], rows=[inst("sum", "revenue", "qk")],
                   mark="Area", color=inst("none", "category_name", "nk")))
# Top 10 products
S.append(worksheet("Top 10 Products", "product_performance",
                   rows=[inst("none", "product_name", "nk")], cols=[inst("sum", "net_revenue", "qk")],
                   mark="Bar", color=inst("none", "category_name", "nk"),
                   filters=[(inst("none", "Calc_Top10", "nk"), "true")],
                   sort=(inst("none", "product_name", "nk"), inst("sum", "net_revenue", "qk"), "DESC"),
                   text=inst("sum", "net_revenue", "qk"), labels=True))
# Category revenue by year
S.append(worksheet("Category Revenue by Year", "order_line_sales",
                   rows=[inst("none", "category_name", "nk")],
                   cols=[inst("yr", "order_date", "ok"), inst("sum", "net_revenue", "qk")], mark="Bar",
                   color=inst("yr", "order_date", "ok"),
                   sort=(inst("none", "category_name", "nk"), inst("sum", "net_revenue", "qk"), "DESC")))
# New vs repeat orders by month
S.append(worksheet("New vs Repeat Orders", "order_summary",
                   cols=[inst("tmn", "order_month", "ok")], rows=[inst("ctd", "order_id", "qk")],
                   mark="Bar", color=inst("none", "new_vs_repeat", "nk")))
# Customer segments
S.append(worksheet("Revenue by Customer Segment", "customer_summary",
                   rows=[inst("none", "customer_segment", "nk")], cols=[inst("sum", "lifetime_value", "qk")],
                   mark="Bar", color=inst("none", "customer_segment", "nk"), text=inst("usr", "Calc_RevShare", "qk"),
                   labels=True,
                   sort=(inst("none", "customer_segment", "nk"), inst("sum", "lifetime_value", "qk"), "DESC")))
# Cohort retention heat-map
S.append(worksheet("Cohort Retention", "cohort_retention",
                   rows=[inst("tqr", "cohort_month", "ok")], cols=[inst("none", "months_since_first", "ok")],
                   mark="Square", color=inst("usr", "Calc_Retention", "qk"), text=inst("usr", "Calc_Retention", "qk"),
                   filters=[(inst("none", "months_since_first", "ok"), [str(m) for m in range(1, 13)])], labels=True))
# Product repeat-buy matrix
S.append(worksheet("Product Repeat-Buy Matrix", "product_performance",
                   cols=[inst("sum", "units_sold", "qk")], rows=[inst("usr", "Calc_RepeatBuyer", "qk")],
                   mark="Circle", color=inst("none", "category_name", "nk"), size=inst("sum", "net_revenue", "qk"),
                   detail=inst("none", "product_name", "nk")))
# Revenue by region
S.append(worksheet("Revenue by Region", "order_line_sales",
                   rows=[inst("none", "region_name", "nk")], cols=[inst("sum", "net_revenue", "qk")], mark="Bar",
                   text=inst("sum", "net_revenue", "qk"), labels=True,
                   sort=(inst("none", "region_name", "nk"), inst("sum", "net_revenue", "qk"), "DESC")))


# ------------------------------------------------------------------ dashboards
_zid = [100]


def zid():
    _zid[0] += 1
    return _zid[0]


def zone_sheet(name, x, y, w, h):
    return (f"          <zone h='{h}' id='{zid()}' name={A(name)} w='{w}' x='{x}' y='{y}'>\n"
            f"            <zone-style>\n              <format attr='border-color' value='#e5e5e5' />\n"
            f"              <format attr='border-style' value='solid' />\n"
            f"              <format attr='border-width' value='1' />\n              <format attr='margin' value='4' />\n"
            f"            </zone-style>\n          </zone>")


def zone_legend(sheet, src, field, x, y, w, h):
    return (f"          <zone h='{h}' id='{zid()}' name={A(sheet)} pane-specification-id='0' "
            f"param={A(f'[{ds_name(src)}].[none:{field}:nk]')} type-v2='color' w='{w}' x='{x}' y='{y}' />")


def zone_text(text, sub, x, y, w, h):
    return (f"          <zone h='{h}' id='{zid()}' type-v2='text' w='{w}' x='{x}' y='{y}'>\n"
            f"            <formatted-text>\n"
            f"              <run bold='true' fontcolor='#4e2a84' fontsize='20'>{escape(text)}</run>\n"
            f"              <run>&#10;</run>\n"
            f"              <run fontcolor='#666666' fontsize='10'>{escape(sub)}</run>\n"
            f"            </formatted-text>\n          </zone>")


def dashboard(name, zones):
    return f"""    <dashboard name={A(name)}>
      <style />
      <size maxheight='800' maxwidth='1200' minheight='800' minwidth='1200' sizing-mode='fixed' />
      <zones>
        <zone h='100000' id='{zid()}' type-v2='layout-basic' w='100000' x='0' y='0'>
{chr(10).join(zones)}
        </zone>
      </zones>
    </dashboard>"""


SUB = "Bertie Sweet Online Shop · Jan 2024 – Dec 2025 · cancelled orders excluded"
D1 = dashboard("Sales Performance", [
    zone_text("Sales Performance", SUB, 0, 0, 100000, 8000),
    zone_sheet("KPI Revenue", 0, 8000, 25000, 14000),
    zone_sheet("KPI Orders", 25000, 8000, 25000, 14000),
    zone_sheet("KPI Avg Order Value", 50000, 8000, 25000, 14000),
    zone_sheet("KPI Repeat Order %", 75000, 8000, 25000, 14000),
    zone_sheet("Revenue Trend by Category", 0, 22000, 86000, 38000),
    zone_legend("Revenue Trend by Category", "monthly_category_revenue", "category_name", 86000, 22000, 14000, 38000),
    zone_sheet("Top 10 Products", 0, 60000, 40000, 40000),
    zone_sheet("Category Revenue by Year", 40000, 60000, 35000, 40000),
    zone_sheet("Revenue by Region", 75000, 60000, 25000, 40000),
])
D2 = dashboard("Customers & Repeat Purchasing", [
    zone_text("Customers & Repeat Purchasing", SUB, 0, 0, 100000, 8000),
    zone_sheet("New vs Repeat Orders", 0, 8000, 46000, 46000),
    zone_legend("New vs Repeat Orders", "order_summary", "new_vs_repeat", 46000, 8000, 9000, 46000),
    zone_sheet("Revenue by Customer Segment", 55000, 8000, 45000, 46000),
    zone_sheet("Cohort Retention", 0, 54000, 55000, 46000),
    zone_sheet("Product Repeat-Buy Matrix", 55000, 54000, 33000, 46000),
    zone_legend("Product Repeat-Buy Matrix", "product_performance", "category_name", 88000, 54000, 12000, 46000),
])

sheet_names = [s.split("name=")[1].split(">")[0].strip("'\"") for s in S]
CARDS = """
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'>
            <card type='columns' />
          </strip>
          <strip size='2147483647'>
            <card type='rows' />
          </strip>
          <strip size='31'>
            <card type='title' />
          </strip>
        </edge>
      </cards>"""
windows = "\n".join(f"    <window class='worksheet' name={A(n)}>{CARDS}\n    </window>" for n in sheet_names)
DASH_SHEETS = {
    "Sales Performance": ["KPI Revenue", "KPI Orders", "KPI Avg Order Value", "KPI Repeat Order %",
                          "Revenue Trend by Category", "Top 10 Products", "Category Revenue by Year",
                          "Revenue by Region"],
    "Customers & Repeat Purchasing": ["New vs Repeat Orders", "Revenue by Customer Segment", "Cohort Retention",
                                      "Product Repeat-Buy Matrix"],
}
for dn, mx in (("Sales Performance", " maximized='true'"), ("Customers & Repeat Purchasing", "")):
    vps = "\n".join(f"        <viewpoint name={A(n)}>\n          <zoom type='entire-view' />\n        </viewpoint>"
                    for n in DASH_SHEETS[dn])
    windows += (f"\n    <window class='dashboard'{mx} name={A(dn)}>\n      <viewpoints>\n{vps}\n      </viewpoints>\n"
                f"      <active id='-1' />\n    </window>")
twb = f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook original-version='18.1' source-build='2026.2.0 (20262.26.0101.0000)' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
  </preferences>
  <datasources>
{datasources}
  </datasources>
  <worksheets>
{chr(10).join(S)}
  </worksheets>
  <dashboards>
{D1}
{D2}
  </dashboards>
  <windows>
{windows}
  </windows>
</workbook>
"""
OUT.write_text(twb, encoding="utf-8")
print("wrote", OUT, len(twb), "bytes")
