import streamlit as st
import numpy as np
import numpy_financial as npf

st.set_page_config(page_title="Legacy Forced Appreciation Calculator", layout="wide")
st.title("🏢 Legacy Forced Appreciation Calculator (Value-Add / BRRRR)")
st.caption("Primary goal: buy deals that support **minimum +20% NOI** through forced appreciation.")

# -----------------------------
# Helpers
# -----------------------------
def safe_div(a, b):
    return a / b if b else 0.0

def annual_debt_service(loan, rate, years):
    if loan <= 0:
        return 0.0
    r = rate / 12
    n = years * 12
    if r == 0:
        return loan / years
    pmt = loan * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    return float(pmt * 12)

def loan_balance_after_years(loan, rate, years_amort, years_elapsed):
    """Annual approximation using annual payment (screening-level)."""
    if loan <= 0:
        return 0.0
    if years_elapsed <= 0:
        return float(loan)
    if rate == 0:
        # straight-line principal
        principal_paid = loan * min(years_elapsed / years_amort, 1.0)
        return float(max(loan - principal_paid, 0.0))

    # approximate annual amortization using annual payment
    A = annual_debt_service(loan, rate, years_amort)
    r = rate
    k = years_elapsed
    # B_k = P*(1+r)^k - A*(((1+r)^k - 1)/r)
    B = loan * (1 + r) ** k - A * (((1 + r) ** k - 1) / r)
    return float(max(B, 0.0))

def fmt_money(x):
    return f"${x:,.0f}"

# -----------------------------
# Sidebar Inputs
# -----------------------------
st.sidebar.header("Deal Basics")
purchase_price = st.sidebar.number_input("Purchase Price ($)", value=2_000_000.0, step=25_000.0)
units = st.sidebar.number_input("Units", value=24, step=1, min_value=1)

st.sidebar.divider()
st.sidebar.header("In-Place Income")
in_place_rent = st.sidebar.number_input("In-Place Rent / Unit (Monthly $)", value=1250.0, step=25.0)
other_income_monthly = st.sidebar.number_input("Other Income (Monthly $)", value=0.0, step=50.0)
vacancy = st.sidebar.number_input("Vacancy (%)", value=8.0, step=0.5) / 100

st.sidebar.divider()
st.sidebar.header("Value-Add Plan (After Stabilization)")
rent_lift = st.sidebar.number_input("Rent Lift / Unit (Monthly $)", value=150.0, step=25.0)
other_income_lift_monthly = st.sidebar.number_input("Other Income Lift (Monthly $)", value=200.0, step=50.0)
vacancy_after = st.sidebar.number_input("Vacancy After (%)", value=6.0, step=0.5) / 100

st.sidebar.divider()
st.sidebar.header("Operating Expenses")
# Keep it simple but powerful: before vs after expense ratio
exp_ratio_before = st.sidebar.number_input("Expense Ratio BEFORE (% of EGI)", value=45.0, step=1.0) / 100
exp_ratio_after = st.sidebar.number_input("Expense Ratio AFTER (% of EGI)", value=40.0, step=1.0) / 100

st.sidebar.divider()
st.sidebar.header("Rehab / Closing / Reserves")
closing_cost_pct = st.sidebar.number_input("Closing Costs (% of Purchase)", value=2.0, step=0.25) / 100
rehab_per_unit = st.sidebar.number_input("Rehab / Unit ($)", value=10_000.0, step=1_000.0)
exterior_rehab = st.sidebar.number_input("Exterior / Other Rehab ($)", value=50_000.0, step=5_000.0)
contingency_pct = st.sidebar.number_input("Rehab Contingency (%)", value=10.0, step=1.0) / 100
initial_reserves = st.sidebar.number_input("Initial Reserves ($)", value=25_000.0, step=5_000.0)

st.sidebar.divider()
st.sidebar.header("Debt: Acquisition + Refi")
acq_ltv = st.sidebar.number_input("Acquisition LTV (%)", value=80.0, step=1.0) / 100
lender_fees_pct = st.sidebar.number_input("Lender Fees (% of Acq Loan)", value=1.0, step=0.25) / 100

refi_ltv = st.sidebar.number_input("Refi LTV (%)", value=75.0, step=1.0) / 100
refi_rate = st.sidebar.number_input("Refi Rate (%)", value=7.25, step=0.25) / 100
amort_years = st.sidebar.number_input("Amortization (Years)", value=30, step=1, min_value=1)

st.sidebar.divider()
st.sidebar.header("Caps + Targets")
cap_refi = st.sidebar.number_input("Refi Cap Rate (%)", value=6.5, step=0.25) / 100
cap_sale = st.sidebar.number_input("Sale Cap Rate (Hold Exit) (%)", value=6.75, step=0.25) / 100
sale_cost_pct = st.sidebar.number_input("Sale Costs (% of Sale Price)", value=3.0, step=0.25) / 100

noi_target_pct = st.sidebar.number_input("NOI Increase Target (%)", value=20.0, step=1.0) / 100
min_dscr = st.sidebar.number_input("Minimum DSCR Target", value=1.20, step=0.05)

st.sidebar.divider()
st.sidebar.header("Optional: Hold Returns")
show_hold = st.sidebar.toggle("Show 5-Year IRR / Equity Multiple", value=True)
hold_years = st.sidebar.number_input("Hold Years", value=5, step=1, min_value=1)
noi_growth_after = st.sidebar.number_input("Annual NOI Growth After Stabilization (%)", value=3.0, step=0.25) / 100

# -----------------------------
# Core Calculations
# -----------------------------
# Rehab / close
base_rehab = units * rehab_per_unit + exterior_rehab
rehab_total = base_rehab * (1 + contingency_pct)
closing_costs = purchase_price * closing_cost_pct

acq_loan = purchase_price * acq_ltv
down_payment = purchase_price - acq_loan
lender_fees = acq_loan * lender_fees_pct

cash_needed_at_close = down_payment + closing_costs + lender_fees + rehab_total + initial_reserves

# Income BEFORE
gpr_before = units * in_place_rent * 12
other_before = other_income_monthly * 12
gpi_before = gpr_before + other_before
vac_loss_before = gpi_before * vacancy
egi_before = gpi_before - vac_loss_before
opex_before = egi_before * exp_ratio_before
noi_before = egi_before - opex_before

# Income AFTER value-add
new_rent = in_place_rent + rent_lift
gpr_after = units * new_rent * 12
other_after = (other_income_monthly + other_income_lift_monthly) * 12
gpi_after = gpr_after + other_after
vac_loss_after = gpi_after * vacancy_after
egi_after = gpi_after - vac_loss_after
opex_after = egi_after * exp_ratio_after
noi_after = egi_after - opex_after

# NOI lift / forced appreciation
noi_increase = noi_after - noi_before
noi_lift_pct = safe_div(noi_increase, noi_before)

value_before = safe_div(noi_before, cap_refi)
value_after = safe_div(noi_after, cap_refi)
value_created = value_after - value_before

# Refi sizing off AFTER NOI (this is forced appreciation thesis)
refi_loan = value_after * refi_ltv
annual_debt = annual_debt_service(refi_loan, refi_rate, amort_years)
dscr = safe_div(noi_after, annual_debt)

# Cash-out and cash left (BRRRR logic)
cash_out = max(refi_loan - acq_loan, 0.0)
cash_left_in_deal = max(cash_needed_at_close - cash_out, 0.0)
cash_out_multiple = safe_div(cash_out, cash_needed_at_close)

# Cash flow to equity (after refi, stabilized)
annual_cashflow = noi_after - annual_debt
monthly_cashflow = annual_cashflow / 12
coc = safe_div(annual_cashflow, cash_left_in_deal)  # cash-on-cash on remaining trapped equity

# Targets
meets_noi_target = noi_lift_pct >= noi_target_pct
meets_dscr_target = dscr >= min_dscr

# What NOI is required to hit +20% (diagnostic)
noi_required_for_target = noi_before * (1 + noi_target_pct)
noi_gap_to_target = max(noi_required_for_target - noi_after, 0.0)

# Rent lift needed per unit to hit target (approx)
# Convert NOI gap to EGI gap using AFTER expense ratio (screening)
# NOI = EGI * (1 - exp_ratio_after)
required_egi_increase = safe_div(noi_gap_to_target, (1 - exp_ratio_after))
required_rent_per_unit_month = safe_div(required_egi_increase, (units * 12))

# -----------------------------
# MAIN VIEW: Forced Appreciation Snapshot
# -----------------------------
st.subheader("Forced Appreciation Snapshot")

m1, m2, m3, m4 = st.columns(4)
m1.metric("NOI (In-Place)", fmt_money(noi_before))
m2.metric("NOI (After Value-Add)", fmt_money(noi_after))
m3.metric("NOI Increase", fmt_money(noi_increase))
m4.metric("NOI Lift %", f"{noi_lift_pct*100:.1f}%")

s1, s2, s3, s4 = st.columns(4)
s1.metric("Value (In-Place @ Refi Cap)", fmt_money(value_before))
s2.metric("Value (After @ Refi Cap)", fmt_money(value_after))
s3.metric("Value Created", fmt_money(value_created))
s4.metric("Target NOI Lift", f"{noi_target_pct*100:.0f}%")

# Pass/Fail bar
st.divider()
p1, p2, p3 = st.columns(3)
p1.metric("NOI Target Met?", "✅ YES" if meets_noi_target else "❌ NO")
p2.metric("DSCR Target Met?", "✅ YES" if meets_dscr_target else "❌ NO")
p3.metric("Stabilized DSCR", f"{dscr:.2f}")

# -----------------------------
# BRRRR / Refi Results
# -----------------------------
st.subheader("BRRRR / Refi Results (Based on After NOI)")

r1, r2, r3, r4 = st.columns(4)
r1.metric("Cash Needed at Close", fmt_money(cash_needed_at_close))
r2.metric("Refi Loan (After)", fmt_money(refi_loan))
r3.metric("Cash-Out (After)", fmt_money(cash_out))
r4.metric("Cash-Out Multiple", f"{cash_out_multiple:.2f}x")

rr1, rr2, rr3, rr4 = st.columns(4)
rr1.metric("Cash Left in Deal", fmt_money(cash_left_in_deal))
rr2.metric("Annual Debt Service", fmt_money(annual_debt))
rr3.metric("Annual Cash Flow (After Debt)", fmt_money(annual_cashflow))
rr4.metric("Monthly Cash Flow", fmt_money(monthly_cashflow))

# Cash-on-cash on remaining equity
st.metric("Cash-on-Cash (on Cash Left in Deal)", f"{coc*100:.2f}%")

# -----------------------------
# Value-Add Requirement Diagnostic
# -----------------------------
st.subheader("20% NOI Target Diagnostic")

d1, d2, d3 = st.columns(3)
d1.metric("NOI Required for +20%", fmt_money(noi_required_for_target))
d2.metric("NOI Gap (If Any)", fmt_money(noi_gap_to_target))
d3.metric("Rent Lift Needed / Unit / Mo (approx)", f"${required_rent_per_unit_month:,.0f}")

st.caption(
    "Rent-lift-needed is a screening estimate using AFTER expense ratio and assumes the NOI gap is solved purely by increasing EGI."
)

# -----------------------------
# Optional Hold Returns (simple, credible)
# -----------------------------
if show_hold:
    st.divider()
    st.subheader("Hold Returns (Screening)")

    # Cashflows: equity invested is cash_left_in_deal (after refi)
    equity_invested = cash_left_in_deal

    # If equity is zero (full cash-out), set small epsilon so math doesn't explode
    if equity_invested <= 0:
        equity_invested = 1.0

    cashflows = [-equity_invested]
    noi_t = noi_after

    for y in range(1, hold_years + 1):
        if y > 1:
            noi_t *= (1 + noi_growth_after)

        cfe = noi_t - annual_debt

        if y == hold_years:
            sale_price = safe_div(noi_t, cap_sale)
            sale_net = sale_price * (1 - sale_cost_pct)
            bal = loan_balance_after_years(refi_loan, refi_rate, amort_years, hold_years)
            net_sale = max(sale_net - bal, 0.0)
            cfe += net_sale

        cashflows.append(cfe)

    irr = float(npf.irr(cashflows))
    total_positive = sum([cf for cf in cashflows if cf > 0])
    equity_multiple = safe_div(total_positive, equity_invested)

    h1, h2, h3 = st.columns(3)
    h1.metric("Projected IRR", f"{irr*100:.1f}%")
    h2.metric("Equity Multiple", f"{equity_multiple:.2f}x")
    h3.metric("Hold Years", str(int(hold_years)))

    st.caption("Hold model is annual screening: NOI grows, debt service held constant, sale uses exit cap + sale costs + remaining loan balance estimate.")

# -----------------------------
# Bottom Notes
# -----------------------------
st.divider()
st.write("### How to use this tool")
st.write(
    "- Focus on **NOI Lift %** and **Value Created** first.\n"
    "- If NOI Lift is below target, use the diagnostic to see the approximate **rent lift needed**.\n"
    "- Then check **DSCR** and **Cash-Out / Cash Left** to confirm the deal supports the forced appreciation thesis.\n"
)

