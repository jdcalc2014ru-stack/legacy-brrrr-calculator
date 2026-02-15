# App.py
import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(
    page_title="Legacy Forced Appreciation Calculator",
    layout="wide",
)

# -----------------------------
# Helpers
# -----------------------------
def fmt_dollars(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "$0"

def fmt_pct(x, decimals=2):
    try:
        return f"{float(x)*100:.{decimals}f}%"
    except Exception:
        return "0.00%"

def fmt_x(x, decimals=2):
    try:
        return f"{float(x):.{decimals}f}x"
    except Exception:
        return "0.00x"

def annual_debt_service(principal, rate_annual, amort_years):
    """Annual P&I payment for fully amortizing loan. If rate=0, straight-line."""
    principal = float(principal)
    r = float(rate_annual)
    n = int(amort_years) * 12
    if principal <= 0:
        return 0.0
    if n <= 0:
        return 0.0
    if r <= 0:
        # no-interest amort
        return (principal / n) * 12.0
    rm = r / 12.0
    pmt_m = principal * rm / (1 - (1 + rm) ** (-n))
    return pmt_m * 12.0

def remaining_balance(principal, rate_annual, amort_years, months_paid):
    """Remaining balance after months_paid payments on fully amortizing loan."""
    principal = float(principal)
    r = float(rate_annual)
    n = int(amort_years) * 12
    m = int(months_paid)

    if principal <= 0:
        return 0.0
    if m <= 0:
        return principal
    if m >= n:
        return 0.0
    if r <= 0:
        # straight-line balance
        return max(principal * (1 - (m / n)), 0.0)

    rm = r / 12.0
    pmt_m = principal * rm / (1 - (1 + rm) ** (-n))
    # amort balance formula
    bal = principal * (1 + rm) ** m - pmt_m * (((1 + rm) ** m - 1) / rm)
    return max(bal, 0.0)

def irr_bisection(cashflows, low=-0.95, high=5.0, tol=1e-7, max_iter=200):
    """
    Robust IRR via bisection.
    Returns None if IRR not bracketed or cashflows invalid.
    """
    cfs = [float(x) for x in cashflows]
    if len(cfs) < 2:
        return None
    if not (any(x < 0 for x in cfs) and any(x > 0 for x in cfs)):
        return None

    def npv(rate):
        return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cfs))

    f_low = npv(low)
    f_high = npv(high)

    # If not bracketed, try to expand high a bit
    if f_low * f_high > 0:
        for h in [10.0, 25.0, 50.0]:
            f_high = npv(h)
            if f_low * f_high <= 0:
                high = h
                break
        else:
            return None

    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return (low + high) / 2

# -----------------------------
# Sidebar Inputs (FOCUSED ON FORCED APPRECIATION)
# -----------------------------
st.title("🏢 Legacy Forced Appreciation Calculator (Value-Add / BRRRR)")
st.caption("Primary screen: **minimum +20% NOI lift** through forced appreciation, then confirm DSCR + refi/cash-out.")

with st.sidebar:
    st.header("Caps + Targets")

    refi_cap = st.number_input("Refi Cap Rate (%)", min_value=1.0, max_value=20.0, value=6.50, step=0.25) / 100
    sale_cap = st.number_input("Sale Cap Rate (Hold Exit) (%)", min_value=1.0, max_value=25.0, value=6.75, step=0.25) / 100
    sale_costs_pct = st.number_input("Sale Costs (% of Sale Price)", min_value=0.0, max_value=10.0, value=3.0, step=0.25) / 100

    noi_lift_target = st.number_input("NOI Increase Target (%)", min_value=0.0, max_value=200.0, value=20.0, step=1.0) / 100
    dscr_target = st.number_input("Minimum DSCR Target", min_value=0.80, max_value=3.00, value=1.25, step=0.05)

    st.divider()
    st.header("Acquisition (In-Place)")

    purchase_price = st.number_input("Purchase Price ($)", min_value=0.0, value=2_000_000.0, step=50_000.0)
    units = st.number_input("Units", min_value=1, value=14, step=1)

    market_rent = st.number_input("Market Rent / Unit / Month ($)", min_value=0.0, value=1100.0, step=25.0)
    vacancy = st.number_input("Vacancy (%)", min_value=0.0, max_value=30.0, value=7.0, step=0.5) / 100

    expense_ratio_inplace = st.number_input("Expense Ratio (In-Place) (%)", min_value=0.0, max_value=90.0, value=45.0, step=1.0) / 100
    expense_ratio_after = st.number_input("Expense Ratio (After Stabilization) (%)", min_value=0.0, max_value=90.0, value=40.0, step=1.0) / 100

    other_income_month = st.number_input("Other Income / Month ($)", min_value=0.0, value=0.0, step=100.0)

    st.divider()
    st.header("Closing + Rehab + Reserves")

    closing_cost_pct = st.number_input("Closing Costs (% of Purchase)", min_value=0.0, max_value=10.0, value=2.0, step=0.25) / 100
    lender_fees_pct = st.number_input("Lender Fees (% of Loan)", min_value=0.0, max_value=5.0, value=1.0, step=0.25) / 100
    initial_reserves = st.number_input("Initial Reserves ($)", min_value=0.0, value=25_000.0, step=5_000.0)

    rehab_per_unit = st.number_input("Rehab per Unit ($)", min_value=0.0, value=7_000.0, step=1_000.0)
    exterior_rehab = st.number_input("Exterior / CapEx Rehab ($)", min_value=0.0, value=20_000.0, step=5_000.0)
    rehab_months = st.number_input("Rehab Months (timeline)", min_value=0, value=6, step=1)

    st.divider()
    st.header("Value-Add Plan")

    noi_lift_assumed = st.number_input("Assumed NOI Lift (%)", min_value=0.0, max_value=200.0, value=20.0, step=1.0) / 100

    st.divider()
    st.header("Debt (Acq + Refi)")

    acq_ltv = st.number_input("Acquisition LTV (%)", min_value=0.0, max_value=90.0, value=80.0, step=1.0) / 100
    refi_ltv = st.number_input("Refi LTV (%)", min_value=0.0, max_value=90.0, value=75.0, step=1.0) / 100

    refi_rate = st.number_input("Refi Rate (%)", min_value=0.0, max_value=20.0, value=7.25, step=0.25) / 100
    amort_years = st.number_input("Amortization (Years)", min_value=1, max_value=40, value=30, step=1)

    st.divider()
    st.header("Optional: Hold Returns (Screening)")
    show_hold = st.toggle("Show Hold Returns (IRR / Multiple)", value=True)
    hold_years = st.number_input("Hold Years", min_value=1, max_value=30, value=5, step=1)
    noi_growth_after = st.number_input("Annual NOI Growth After Stabilization (%)", min_value=-10.0, max_value=20.0, value=3.0, step=0.5) / 100

# -----------------------------
# Core Calculations
# -----------------------------
# Income
gpr_annual = units * market_rent * 12.0
egi_annual = (gpr_annual + other_income_month * 12.0) * (1 - vacancy)

noi_inplace = egi_annual * (1 - expense_ratio_inplace)
noi_after = egi_annual * (1 - expense_ratio_after) * (1 + noi_lift_assumed)

noi_increase = noi_after - noi_inplace
noi_lift_pct = (noi_increase / noi_inplace) if noi_inplace > 0 else 0.0

noi_required_for_target = noi_inplace * (1 + noi_lift_target)
noi_gap = max(noi_required_for_target - noi_after, 0.0)

# Diagnostic: rent lift per unit per month to close NOI gap (simple screening; assumes gap solved purely by EGI increases, expense ratio uses AFTER)
# NOI = EGI * (1-exp_ratio_after) => EGI needed = NOI / (1-exp_ratio_after)
rent_lift_per_unit_month = 0.0
if units > 0 and (1 - expense_ratio_after) > 0:
    egi_gap = noi_gap / (1 - expense_ratio_after)
    # egi_gap is annual; translate to monthly GPR per unit (ignoring vacancy interaction for simplicity)
    rent_lift_per_unit_month = (egi_gap / 12.0) / units

# Value creation via cap rates
value_inplace_refi_cap = (noi_inplace / refi_cap) if refi_cap > 0 else 0.0
value_after_refi_cap = (noi_after / refi_cap) if refi_cap > 0 else 0.0
value_created = max(value_after_refi_cap - value_inplace_refi_cap, 0.0)

# Deal costs
acq_loan = purchase_price * acq_ltv
down_payment = purchase_price - acq_loan
closing_costs = purchase_price * closing_cost_pct
lender_fees = acq_loan * lender_fees_pct
total_rehab = rehab_per_unit * units + exterior_rehab

cash_needed_at_close = down_payment + closing_costs + lender_fees + total_rehab + initial_reserves

# Refi
refi_loan = value_after_refi_cap * refi_ltv
annual_debt = annual_debt_service(refi_loan, refi_rate, amort_years)
dscr = (noi_after / annual_debt) if annual_debt > 0 else 0.0

# Cash-out math (simple BRRRR: refi pays off acquisition loan; remaining becomes cash-out)
cash_out = max(refi_loan - acq_loan, 0.0)

# Capital left in deal (use close cash vs cash-out)
cash_left_in_deal = max(cash_needed_at_close - cash_out, 0.0)
cash_out_multiple = (cash_out / cash_needed_at_close) if cash_needed_at_close > 0 else 0.0

# Cashflow after refi debt
annual_cfb = noi_after - annual_debt
monthly_cfb = annual_cfb / 12.0

# Targets
noi_target_met = noi_lift_pct >= noi_lift_target
dscr_target_met = dscr >= dscr_target

# -----------------------------
# Layout / Output
# -----------------------------
st.subheader("Forced Appreciation Snapshot")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("NOI (In-Place)", fmt_dollars(noi_inplace))
c2.metric("NOI (After Value-Add)", fmt_dollars(noi_after))
c3.metric("NOI Increase", fmt_dollars(noi_increase))
c4.metric("NOI Lift %", f"{noi_lift_pct*100:,.1f}%")
c5.metric("Target NOI Lift", f"{noi_lift_target*100:,.0f}%")

v1, v2, v3, v4 = st.columns(4)
v1.metric("Value (In-Place @ Refi Cap)", fmt_dollars(value_inplace_refi_cap))
v2.metric("Value (After @ Refi Cap)", fmt_dollars(value_after_refi_cap))
v3.metric("Value Created", fmt_dollars(value_created))
v4.metric("Rent Lift Needed / Unit / Mo (approx)", fmt_dollars(rent_lift_per_unit_month))

t1, t2, t3 = st.columns(3)
t1.markdown(f"### NOI Target Met?\n{'✅ **YES**' if noi_target_met else '❌ **NO**'}")
t2.markdown(f"### DSCR Target Met?\n{'✅ **YES**' if dscr_target_met else '❌ **NO**'}")
t3.metric("Stabilized DSCR", f"{dscr:,.2f}")

st.divider()
st.subheader("BRRRR / Refi Results (Based on AFTER NOI)")

r1, r2, r3, r4 = st.columns(4)
r1.metric("Cash Needed at Close", fmt_dollars(cash_needed_at_close))
r2.metric("Refi Loan (After)", fmt_dollars(refi_loan))
r3.metric("Cash-Out (After)", fmt_dollars(cash_out))
r4.metric("Cash-Out Multiple", fmt_x(cash_out_multiple))

r5, r6, r7 = st.columns(3)
r5.metric("Cash Left in Deal", fmt_dollars(cash_left_in_deal))
r6.metric("Annual Debt Service", fmt_dollars(annual_debt))
r7.metric("Annual Cash Flow (After Debt)", fmt_dollars(annual_cfb))

m1, m2 = st.columns(2)
m1.metric("Monthly Cash Flow (After Debt)", fmt_dollars(monthly_cfb))
m2.caption("Note: This is a simplified screening model (no rent-step timing, no IO bridge phase, no tax impacts).")

# -----------------------------
# Hold Returns (Screening)
# -----------------------------
if show_hold:
    st.divider()
    st.subheader("Hold Returns (Screening)")

    # Build annual cashflows for hold model
    # We anchor returns on ORIGINAL cash needed (pre-refi) to avoid zero-equity blowups.
    equity_base = cash_needed_at_close

    # Treat cash-out as a distribution at end of rehab (year ~ rehab_months/12). For screening, drop into Year 1.
    # (This prevents year-0 cancellation that can explode IRR.)
    cashflows = []
    cashflows.append(-equity_base)  # Year 0

    # Annual cashflow years 1..hold_years
    # NOI grows after stabilization; we start Year 1 at stabilized NOI_after
    # Debt service constant.
    for yr in range(1, int(hold_years) + 1):
        noi_y = noi_after * ((1 + noi_growth_after) ** (yr - 1))
        cfb_y = noi_y - annual_debt
        cashflows.append(cfb_y)

    # Add cash-out to Year 1 cashflow (screening assumption: refi happens within first year after rehab)
    if len(cashflows) > 1:
        cashflows[1] += cash_out

    # Sale proceeds at end of hold
    noi_sale = noi_after * ((1 + noi_growth_after) ** (int(hold_years) - 1))
    sale_price = (noi_sale / sale_cap) if sale_cap > 0 else 0.0
    sale_costs = sale_price * sale_costs_pct

    months_paid = int(hold_years) * 12
    loan_bal = remaining_balance(refi_loan, refi_rate, amort_years, months_paid)

    net_sale_proceeds = max(sale_price - sale_costs - loan_bal, 0.0)
    cashflows[-1] += net_sale_proceeds

    # Metrics (anchored)
    irr_val = irr_bisection(cashflows)
    total_distributions = sum(cf for cf in cashflows[1:] if cf > 0)
    equity_multiple = (total_distributions / equity_base) if equity_base > 0 else 0.0
    coc_year1 = (cashflows[1] / equity_base) if equity_base > 0 else 0.0

    h1, h2, h3 = st.columns(3)
    h1.metric("Cash-on-Cash (Year 1) (anchored)", f"{coc_year1*100:,.2f}%")
    h2.metric("Projected IRR (anchored)", f"{(irr_val*100):,.2f}%" if irr_val is not None else "N/A")
    h3.metric("Equity Multiple (anchored)", fmt_x(equity_multiple))

    with st.expander("Show Assumptions + Cashflows"):
        st.write("**Cashflow convention (annual):** Year 0 = -Cash Needed at Close. Year 1 includes Cash-Out + Year 1 Cash Flow. Final year includes Net Sale Proceeds.")
        df = pd.DataFrame(
            {
                "Year": list(range(0, int(hold_years) + 1)),
                "Cash Flow": cashflows,
            }
        )
        df["Cash Flow (Formatted)"] = df["Cash Flow"].map(fmt_dollars)
        st.dataframe(df[["Year", "Cash Flow (Formatted)"]], use_container_width=True)

        st.write("**Sale / Loan Detail:**")
        dfd = pd.DataFrame(
            {
                "Metric": [
                    "NOI at Sale (Year N)",
                    "Sale Cap",
                    "Sale Price (Gross)",
                    "Sale Costs",
                    "Remaining Loan Balance",
                    "Net Sale Proceeds",
                ],
                "Value": [
                    fmt_dollars(noi_sale),
                    f"{sale_cap*100:,.2f}%",
                    fmt_dollars(sale_price),
                    fmt_dollars(sale_costs),
                    fmt_dollars(loan_bal),
                    fmt_dollars(net_sale_proceeds),
                ],
            }
        )
        st.dataframe(dfd, use_container_width=True)

# -----------------------------
# Quick explanation (why DSCR target might fail)
# -----------------------------
st.divider()
st.subheader("Why DSCR Target Might Not Be Met (Quick Read)")

st.write(
    """
DSCR is **NOI(after value-add) ÷ Annual Debt Service**.
If DSCR is below target, it's usually because one (or more) of these is too aggressive:

- **Refi loan too large** (high Refi LTV or high valuation assumptions)
- **Interest rate too high** / amort too short → **higher debt service**
- **NOI after value-add still too low** (rent lift or expense improvements not strong enough)
- **Cap rate assumptions** (refi cap too tight can inflate value; but DSCR is still constrained by debt payment)

**Fast levers:** lower Refi LTV, increase NOI lift, extend amortization, or assume a slightly higher refi cap (more conservative value).
"""
)
)

