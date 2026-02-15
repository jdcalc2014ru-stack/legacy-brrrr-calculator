# App.py
import streamlit as st
import numpy as np

st.set_page_config(page_title="Legacy Forced Appreciation Calculator", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def pmt(annual_rate: float, amort_years: int, principal: float) -> float:
    """Annual debt service (positive number)."""
    r = annual_rate
    n = amort_years
    if principal <= 0:
        return 0.0
    if r <= 0:
        return principal / n
    return (r * principal) / (1 - (1 + r) ** (-n))

def annual_payment_from_monthly(monthly_rate: float, n_months: int, principal: float) -> float:
    if principal <= 0:
        return 0.0
    if monthly_rate <= 0:
        m = principal / n_months
        return m * 12.0
    m = (monthly_rate * principal) / (1 - (1 + monthly_rate) ** (-n_months))
    return m * 12.0

def monthly_payment(monthly_rate: float, n_months: int, principal: float) -> float:
    if principal <= 0:
        return 0.0
    if monthly_rate <= 0:
        return principal / n_months
    return (monthly_rate * principal) / (1 - (1 + monthly_rate) ** (-n_months))

def remaining_balance(principal: float, annual_rate: float, amort_years: int, years_elapsed: float) -> float:
    """Remaining loan balance after years_elapsed (with monthly amortization)."""
    if principal <= 0:
        return 0.0
    n_total = int(amort_years * 12)
    n_paid = int(round(years_elapsed * 12))
    n_paid = max(0, min(n_paid, n_total))

    r_m = annual_rate / 12.0
    pay_m = monthly_payment(r_m, n_total, principal)

    if r_m <= 0:
        return max(principal - pay_m * n_paid, 0.0)

    # Balance formula: B_k = P*(1+r)^k - PMT*(((1+r)^k - 1)/r)
    growth = (1 + r_m) ** n_paid
    bal = principal * growth - pay_m * ((growth - 1) / r_m)
    return max(bal, 0.0)

def irr_newton(cashflows, guess=0.12) -> float:
    """
    Robust-ish IRR via Newton-Raphson on annual periods.
    Returns decimal (0.15 = 15%). Returns np.nan if not solvable.
    """
    cfs = np.array(cashflows, dtype=float)
    if len(cfs) < 2:
        return np.nan
    if not (np.any(cfs > 0) and np.any(cfs < 0)):
        return np.nan

    r = guess
    for _ in range(80):
        denom = (1 + r) ** np.arange(len(cfs))
        npv = np.sum(cfs / denom)

        # d/d r of cfs/(1+r)^t = -t*cfs/(1+r)^(t+1)
        d = -np.sum((np.arange(len(cfs)) * cfs) / ((1 + r) ** (np.arange(len(cfs)) + 1)))

        if abs(d) < 1e-10:
            break

        r_next = r - npv / d

        # Keep r from going below -99% (math breaks at -100%)
        if r_next <= -0.99:
            r_next = (r - 0.99) / 2.0

        if abs(r_next - r) < 1e-8:
            r = r_next
            break
        r = r_next

    # sanity: if absurd, return nan
    if not np.isfinite(r) or r > 5 or r <= -0.99:
        return np.nan
    return r

def money(x: float) -> str:
    return f"${x:,.0f}"

def pct(x: float, digits=2) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{x*100:.{digits}f}%"

# -----------------------------
# Sidebar Inputs
# -----------------------------
st.title("🏢 Legacy Forced Appreciation Calculator (Value-Add / BRRRR)")
st.caption("Primary goal: screen deals that can support **minimum +20% NOI** through forced appreciation (rent lift + expense improvements + other NOI).")

with st.sidebar:
    st.header("Caps + Targets")

    refi_cap = st.number_input("Refi Cap Rate (%)", min_value=1.0, max_value=20.0, value=6.50, step=0.25) / 100.0
    sale_cap = st.number_input("Sale Cap Rate (Hold Exit) (%)", min_value=1.0, max_value=20.0, value=6.75, step=0.25) / 100.0
    sale_cost_pct = st.number_input("Sale Costs (% of Sale Price)", min_value=0.0, max_value=15.0, value=3.0, step=0.25) / 100.0

    noi_target_pct = st.number_input("NOI Increase Target (%)", min_value=0.0, max_value=200.0, value=20.0, step=1.0) / 100.0
    dscr_target = st.number_input("Minimum DSCR Target", min_value=0.50, max_value=3.00, value=1.25, step=0.05)

    st.divider()
    st.header("Deal + Income (In-Place ➜ After)")

    purchase_price = st.number_input("Purchase Price ($)", min_value=0.0, value=2_000_000.0, step=50_000.0)
    units = st.number_input("Units", min_value=1, value=14, step=1)

    inplace_rent = st.number_input("In-Place Rent / Unit / Month ($)", min_value=0.0, value=1050.0, step=25.0)
    rent_raise = st.number_input("Planned Rent Raise / Unit / Month ($)", min_value=0.0, value=150.0, step=25.0)
    after_rent = inplace_rent + rent_raise

    other_income_unit = st.number_input("Other Income / Unit / Month ($)", min_value=0.0, value=0.0, step=10.0)

    vacancy = st.number_input("Vacancy (%)", min_value=0.0, max_value=50.0, value=7.0, step=0.5) / 100.0

    # Expense ratios (simple screening)
    expense_ratio_in = st.number_input("Expense Ratio (In-Place) (%)", min_value=0.0, max_value=90.0, value=45.0, step=1.0) / 100.0
    expense_ratio_after = st.number_input("Expense Ratio (After) (%)", min_value=0.0, max_value=90.0, value=42.0, step=1.0) / 100.0

    # Extra NOI lift beyond rent raise + expense ratio change (ops improvements, fees, RUBS, etc.)
    extra_noi_lift = st.number_input("Extra NOI Lift Beyond Rent (%)", min_value=0.0, max_value=200.0, value=0.0, step=1.0) / 100.0

    st.divider()
    st.header("Rehab + Closing")

    rehab_per_unit = st.number_input("Rehab per Unit ($)", min_value=0.0, value=7_000.0, step=1_000.0)
    exterior_rehab = st.number_input("Exterior / Common Rehab ($)", min_value=0.0, value=20_000.0, step=5_000.0)
    rehab_months = st.number_input("Rehab Months (screening)", min_value=0, value=6, step=1)

    closing_cost_pct = st.number_input("Closing Costs (% of Purchase)", min_value=0.0, max_value=10.0, value=2.0, step=0.25) / 100.0
    lender_fee_pct = st.number_input("Lender Fees (% of Loan)", min_value=0.0, max_value=10.0, value=1.0, step=0.25) / 100.0
    reserves = st.number_input("Initial Reserves ($)", min_value=0.0, value=25_000.0, step=5_000.0)

    st.divider()
    st.header("Debt Assumptions (Acq ➜ Refi)")

    acq_ltv = st.number_input("Acquisition LTV (%)", min_value=0.0, max_value=95.0, value=80.0, step=1.0) / 100.0
    acq_interest_only = st.checkbox("Acquisition Loan is Interest-Only (screening)", value=True)
    acq_rate = st.number_input("Acquisition Rate (%)", min_value=0.0, max_value=20.0, value=9.5, step=0.25) / 100.0  # only used if not interest-only

    refi_ltv = st.number_input("Refi LTV (%)", min_value=0.0, max_value=85.0, value=75.0, step=1.0) / 100.0
    refi_rate = st.number_input("Refi Rate (%)", min_value=0.0, max_value=20.0, value=7.25, step=0.25) / 100.0
    amort_years = st.number_input("Amortization (Years)", min_value=1, value=30, step=1)

    st.divider()
    st.header("Optional: Hold Returns (Screening)")

    show_hold = st.toggle("Show 5–10yr IRR / Equity Multiple", value=True)
    hold_years = st.number_input("Hold Years", min_value=1, value=5, step=1)
    noi_growth = st.number_input("Annual NOI Growth After Stabilization (%)", min_value=0.0, max_value=20.0, value=3.0, step=0.25) / 100.0

# -----------------------------
# Core Calculations
# -----------------------------
rehab_total = rehab_per_unit * units + exterior_rehab
closing_costs = purchase_price * closing_cost_pct

# Acquisition loan basis (simple screening):
# We assume the acquisition lender funds a % of (purchase + rehab) as "total project cost" financing.
total_project_cost = purchase_price + rehab_total
acq_loan = total_project_cost * acq_ltv

# Lender fees based on acquisition loan
lender_fees = acq_loan * lender_fee_pct

# Cash needed at close (your money in)
# Down payment on project cost + closing + lender fees + reserves
down_payment = max(total_project_cost - acq_loan, 0.0)
cash_needed_at_close = down_payment + closing_costs + lender_fees + reserves

# Income - In-place
gpr_inplace = units * inplace_rent * 12.0
other_income_annual = units * other_income_unit * 12.0
egi_inplace = (gpr_inplace + other_income_annual) * (1 - vacancy)
noi_inplace = egi_inplace * (1 - expense_ratio_in)

# Income - After (rent raise + expenses + extra NOI lift)
gpr_after = units * after_rent * 12.0
egi_after = (gpr_after + other_income_annual) * (1 - vacancy)
noi_after_base = egi_after * (1 - expense_ratio_after)
noi_after = noi_after_base * (1 + extra_noi_lift)

# Forced appreciation value created
value_inplace = noi_inplace / refi_cap if refi_cap > 0 else 0.0
value_after = noi_after / refi_cap if refi_cap > 0 else 0.0
value_created = max(value_after - value_inplace, 0.0)

noi_increase = noi_after - noi_inplace
noi_lift_pct = (noi_increase / noi_inplace) if noi_inplace > 0 else np.nan
noi_target_met = (noi_lift_pct >= noi_target_pct) if np.isfinite(noi_lift_pct) else False

# Diagnostic: rent lift needed per unit/month (approx) to hit NOI target using AFTER expense ratio + vacancy
required_noi = noi_inplace * (1 + noi_target_pct)
# reverse out the extra lift multiplier first (so rent/EGI solves for base)
required_noi_base = required_noi / (1 + extra_noi_lift) if (1 + extra_noi_lift) > 0 else required_noi

required_egi_after = required_noi_base / (1 - expense_ratio_after) if (1 - expense_ratio_after) > 0 else np.inf
required_gpr_after = required_egi_after / (1 - vacancy) - other_income_annual if (1 - vacancy) > 0 else np.inf

required_rent_after = (required_gpr_after / 12.0) / units if units > 0 else np.inf
rent_lift_needed = max(required_rent_after - inplace_rent, 0.0) if np.isfinite(required_rent_after) else np.nan
noi_gap = max(required_noi - noi_after, 0.0) if np.isfinite(required_noi) else np.nan

# Refi loan based on AFTER value (this is the whole forced appreciation point)
refi_loan = value_after * refi_ltv

# Annual debt service on refi loan
annual_debt = annual_payment_from_monthly(refi_rate / 12.0, int(amort_years * 12), refi_loan)

dscr_after = (noi_after / annual_debt) if annual_debt > 0 else np.nan
dscr_met = (dscr_after >= dscr_target) if np.isfinite(dscr_after) else False

# Cash-out: refi pays off acquisition loan
cash_out = max(refi_loan - acq_loan, 0.0)

# Equity remaining / cash left in deal:
# If cash_out is less than your cash_in, you still have cash left in.
cash_left_in_deal = max(cash_needed_at_close - cash_out, 0.0)

cash_out_multiple = (cash_out / cash_needed_at_close) if cash_needed_at_close > 0 else 0.0

# Property cashflow (after stabilization) - simple annual
annual_cashflow_after_debt = noi_after - annual_debt
monthly_cashflow_after_debt = annual_cashflow_after_debt / 12.0

# -----------------------------
# Investor Return Metrics (simple)
# -----------------------------
# Cash-on-cash (Year 1) based on remaining equity left in deal after refi
equity_invested_net = cash_left_in_deal  # remaining equity after cash-out
coc = (annual_cashflow_after_debt / equity_invested_net) if equity_invested_net > 0 else np.nan

# Hold returns screening (optional)
projected_irr = np.nan
equity_multiple = np.nan

if show_hold:
    # Build annual cash flows:
    # Year 0: -cash_needed_at_close
    # Year 1: +cash_out + year1 cashflow (after debt)
    # Years 2..hold_years-1: growing cashflow
    # Final year: cashflow + net sale proceeds
    cfs = []
    cfs.append(-cash_needed_at_close)

    # year 1 cash flow
    y1_cf = annual_cashflow_after_debt
    cfs.append(cash_out + y1_cf)

    # intermediate years
    cf = y1_cf
    for _y in range(2, hold_years + 1):
        cf *= (1 + noi_growth)
        cfs.append(cf)

    # Sale at end of hold_years
    # Sale price uses sale cap on NOI in final year (we used cf as after-debt; rebuild NOI for exit)
    # Compute NOI in final year by growing NOI_after (before debt) by noi_growth^(hold_years-1)
    noi_exit = noi_after * ((1 + noi_growth) ** max(hold_years - 1, 0))
    sale_price = (noi_exit / sale_cap) if sale_cap > 0 else 0.0
    sale_costs = sale_price * sale_cost_pct

    # Remaining loan balance on refi loan after hold_years years
    loan_bal = remaining_balance(refi_loan, refi_rate, amort_years, hold_years)

    net_sale_proceeds = max(sale_price - sale_costs - loan_bal, 0.0)

    # Add sale proceeds to last year cash flow
    cfs[-1] = cfs[-1] + net_sale_proceeds

    projected_irr = irr_newton(cfs, guess=0.15)

    total_distributions = np.sum([x for x in cfs if x > 0])
    equity_multiple = (total_distributions / cash_needed_at_close) if cash_needed_at_close > 0 else np.nan

# -----------------------------
# Layout / Output
# -----------------------------
# Top snapshot
st.subheader("Forced Appreciation Snapshot")

c1, c2, c3, c4 = st.columns(4)
c1.metric("NOI (In-Place)", money(noi_inplace))
c2.metric("NOI (After Value-Add)", money(noi_after))
c3.metric("NOI Increase", money(noi_increase))
c4.metric("NOI Lift %", "—" if not np.isfinite(noi_lift_pct) else f"{noi_lift_pct*100:.1f}%")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Value (In-Place @ Refi Cap)", money(value_inplace))
c6.metric("Value (After @ Refi Cap)", money(value_after))
c7.metric("Value Created", money(value_created))
c8.metric("Target NOI Lift", f"{noi_target_pct*100:.0f}%")

st.caption(
    f"Rent Plan: In-Place {money(inplace_rent)}/unit/mo → After {money(after_rent)}/unit/mo "
    f"(Raise: {money(rent_raise)}/unit/mo). Extra NOI Lift Beyond Rent: {extra_noi_lift*100:.0f}%."
)

flag1, flag2, flag3 = st.columns([1, 1, 1])
flag1.markdown(f"### NOI Target Met?\n{'✅ **YES**' if noi_target_met else '❌ **NO**'}")
flag2.markdown(f"### DSCR Target Met?\n{'✅ **YES**' if dscr_met else '❌ **NO**'}")
flag3.markdown(f"### Stabilized DSCR\n**{'—' if not np.isfinite(dscr_after) else f'{dscr_after:.2f}'}**")

st.divider()

# BRRRR / Refi results
st.subheader("BRRRR / Refi Results (Based on AFTER NOI)")

r1, r2, r3, r4 = st.columns(4)
r1.metric("Cash Needed at Close", money(cash_needed_at_close))
r2.metric("Refi Loan (After)", money(refi_loan))
r3.metric("Cash-Out (After)", money(cash_out))
r4.metric("Cash-Out Multiple", f"{cash_out_multiple:.2f}x")

r5, r6, r7, r8 = st.columns(4)
r5.metric("Cash Left in Deal", money(cash_left_in_deal))
r6.metric("Annual Debt Service", money(annual_debt))
r7.metric("Annual Cash Flow (After Debt)", money(annual_cashflow_after_debt))
r8.metric("Monthly Cash Flow", money(monthly_cashflow_after_debt))

st.divider()

# Investor return metrics
st.subheader("Investor Return Metrics (Screening)")

m1, m2, m3 = st.columns(3)
m1.metric("Cash-on-Cash (Year 1)", "—" if not np.isfinite(coc) else f"{coc*100:.2f}%")
m2.metric("IRR (Projected)", "—" if not np.isfinite(projected_irr) else f"{projected_irr*100:.2f}%")
m3.metric("Equity Multiple", "—" if not np.isfinite(equity_multiple) else f"{equity_multiple:.2f}x")

# Diagnostics + detailed cashflows
with st.expander("Show Assumptions + Cashflows"):
    d1, d2, d3 = st.columns(3)
    d1.metric("NOI Required for +Target", money(required_noi))
    d2.metric("NOI Gap (If Any)", money(noi_gap))
    d3.metric("Rent Lift Needed / Unit / Mo (approx)", "—" if not np.isfinite(rent_lift_needed) else money(rent_lift_needed))

    st.markdown("#### Income Breakdown (Annual)")
    b1, b2 = st.columns(2)

    with b1:
        st.write("**In-Place**")
        st.write(f"GPR: {money(gpr_inplace)}")
        st.write(f"Other Income: {money(other_income_annual)}")
        st.write(f"EGI (after vacancy): {money(egi_inplace)}")
        st.write(f"Expense Ratio: {expense_ratio_in*100:.1f}%")
        st.write(f"NOI: {money(noi_inplace)}")

    with b2:
        st.write("**After Value-Add**")
        st.write(f"GPR: {money(gpr_after)}")
        st.write(f"Other Income: {money(other_income_annual)}")
        st.write(f"EGI (after vacancy): {money(egi_after)}")
        st.write(f"Expense Ratio: {expense_ratio_after*100:.1f}%")
        st.write(f"NOI (base): {money(noi_after_base)}")
        st.write(f"Extra NOI Lift Beyond Rent: {extra_noi_lift*100:.1f}%")
        st.write(f"NOI (after): {money(noi_after)}")

    st.markdown("#### Capital Stack (Screening)")
    st.write(f"Rehab Total: {money(rehab_total)}")
    st.write(f"Total Project Cost (Purchase + Rehab): {money(total_project_cost)}")
    st.write(f"Acquisition Loan: {money(acq_loan)} (Acq LTV: {acq_ltv*100:.1f}%)")
    st.write(f"Down Payment: {money(down_payment)}")
    st.write(f"Closing Costs: {money(closing_costs)}")
    st.write(f"Lender Fees: {money(lender_fees)}")
    st.write(f"Reserves: {money(reserves)}")

    if show_hold:
        st.markdown("#### Hold Cashflows (Annual, Screening)")
        # Rebuild cashflows table (same as above)
        cfs_table = []
        cfs_table.append(("Year 0", -cash_needed_at_close))
        y1_cf = annual_cashflow_after_debt
        cfs_table.append(("Year 1 (Cash-Out + CF)", cash_out + y1_cf))

        cf = y1_cf
        for y in range(2, hold_years):
            cf *= (1 + noi_growth)
            cfs_table.append((f"Year {y}", cf))

        # final year includes sale
        noi_exit = noi_after * ((1 + noi_growth) ** max(hold_years - 1, 0))
        sale_price = (noi_exit / sale_cap) if sale_cap > 0 else 0.0
        sale_costs = sale_price * sale_cost_pct
        loan_bal = remaining_balance(refi_loan, refi_rate, amort_years, hold_years)
        net_sale_proceeds = max(sale_price - sale_costs - loan_bal, 0.0)

        cf_final = (annual_cashflow_after_debt * ((1 + noi_growth) ** max(hold_years - 1, 0))) + net_sale_proceeds
        cfs_table.append((f"Year {hold_years} (CF + Sale)", cf_final))

        st.write(f"Sale Price (Exit NOI / Sale Cap): {money(sale_price)}")
        st.write(f"Sale Costs: {money(sale_costs)}")
        st.write(f"Remaining Loan Balance (approx): {money(loan_bal)}")
        st.write(f"Net Sale Proceeds (approx): {money(net_sale_proceeds)}")

        # display table
        st.table([(y, money(v)) for y, v in cfs_table])

st.divider()
st.caption(
    "Note: This is a screening calculator (not a full underwriting model). "
    "It’s designed to quickly answer: **can we force NOI up by 20%+ and still meet DSCR + cash-out goals?**"
)


