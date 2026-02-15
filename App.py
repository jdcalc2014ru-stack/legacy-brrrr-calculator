import streamlit as st
import numpy as np

# -----------------------------
# Legacy Family Fund BRRRR Calculator (Single File App.py)
# -----------------------------

st.set_page_config(page_title="Legacy BRRRR Calculator", layout="wide")
st.title("🏢 Legacy Family Fund BRRRR Calculator")

# -----------------------------
# Sidebar Inputs
# -----------------------------
st.sidebar.header("Acquisition")

st.sidebar.subheader("Closing & Reserves")
closing_cost_pct = st.sidebar.number_input("Closing Costs (% of Purchase)", value=2.0, step=0.25) / 100
lender_fees_pct = st.sidebar.number_input("Lender Fees (% of Loan)", value=1.0, step=0.25) / 100
initial_reserves = st.sidebar.number_input("Initial Reserves ($)", value=25000.0, step=5000.0)

purchase_price = st.sidebar.number_input("Purchase Price ($)", value=2000000.0, step=50000.0)
units = st.sidebar.number_input("Units", value=14, step=1, min_value=1)
rent = st.sidebar.number_input("Market Rent per Unit ($/month)", value=1100.0, step=25.0)
vacancy = st.sidebar.number_input("Vacancy (%)", value=7.0, step=0.5) / 100

st.sidebar.header("Rehab")
rehab_months = st.sidebar.number_input("Rehab Months", value=6, step=1, min_value=0)
rehab_per_unit = st.sidebar.number_input("Rehab per Unit ($)", value=7000.0, step=500.0)
exterior_rehab = st.sidebar.number_input("Exterior Rehab ($)", value=0.0, step=5000.0)

st.sidebar.header("Financing")
st.sidebar.subheader("Acquisition Loan")
acq_ltv = st.sidebar.number_input("Acquisition LTV (%)", value=80.0, step=1.0, min_value=0.0, max_value=100.0) / 100

st.sidebar.subheader("Refi Assumptions")
exit_cap = st.sidebar.number_input("Exit Cap Rate (%)", value=7.0, step=0.25, min_value=0.1) / 100
refi_ltv = st.sidebar.number_input("Refi LTV (%)", value=75.0, step=1.0, min_value=0.0, max_value=100.0) / 100
refi_rate = st.sidebar.number_input("Refi Rate (%)", value=7.25, step=0.25, min_value=0.0) / 100
amort_years = st.sidebar.number_input("Amortization (Years)", value=30, step=1, min_value=1)

st.sidebar.header("Operating Assumptions")
expense_ratio = st.sidebar.number_input("Expense Ratio (%)", value=40.0, step=1.0, min_value=0.0, max_value=100.0) / 100

st.sidebar.header("Investor Return Assumptions")
hold_years = st.sidebar.number_input("Hold Period (Years)", value=7, step=1, min_value=1)
noi_growth = st.sidebar.number_input("NOI Growth (%/yr)", value=3.0, step=0.25, min_value=-50.0, max_value=50.0) / 100
exit_cap_sale = st.sidebar.number_input("Exit Cap at Sale (%)", value=float(exit_cap * 100), step=0.25, min_value=0.1) / 100
sale_cost_pct = st.sidebar.number_input("Sale Costs (% of Sale Price)", value=2.0, step=0.25, min_value=0.0, max_value=20.0) / 100

# -----------------------------
# Helper Functions
# -----------------------------
def annual_payment(rate: float, nper_years: int, pv: float) -> float:
    """Annual mortgage payment for a fully-amortizing loan."""
    if pv <= 0:
        return 0.0
    if rate <= 0:
        return pv / nper_years
    return (rate * pv) / (1 - (1 + rate) ** (-nper_years))

def safe_irr(cashflows: list[float]) -> float:
    """
    Robust IRR using bisection (no numpy_financial required).
    Returns np.nan if IRR can't be found.
    """
    # Need at least one negative and one positive cashflow
    if not (any(cf < 0 for cf in cashflows) and any(cf > 0 for cf in cashflows)):
        return np.nan

    def npv(r: float) -> float:
        return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cashflows))

    low, high = -0.999, 10.0  # allow very high IRRs
    f_low, f_high = npv(low), npv(high)

    # If no sign change, can't guarantee a root
    if np.isnan(f_low) or np.isnan(f_high) or (f_low * f_high > 0):
        return np.nan

    for _ in range(200):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-8:
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid
    return (low + high) / 2

# -----------------------------
# Calculations
# -----------------------------

# Acquisition loan and cash needed at close
acq_loan = purchase_price * acq_ltv
down_payment = purchase_price - acq_loan
purchase_closing_costs = purchase_price * closing_cost_pct
lender_fees = acq_loan * lender_fees_pct

total_rehab = rehab_per_unit * units + exterior_rehab

cash_needed_at_close = down_payment + purchase_closing_costs + lender_fees + total_rehab + initial_reserves

# Stabilized NOI (simple pro-forma)
gross_rent = units * rent * 12
effective_income = gross_rent * (1 - vacancy)
expenses = effective_income * expense_ratio
noi = effective_income - expenses

# Value and refi loan
stabilized_value = noi / exit_cap if exit_cap > 0 else 0.0
refi_loan = stabilized_value * refi_ltv

# Refi debt service and DSCR
annual_debt = annual_payment(refi_rate, int(amort_years), refi_loan)
dscr = (noi / annual_debt) if annual_debt > 0 else np.nan

# -----------------------------
# Correct BRRRR refinance proceeds math
# -----------------------------
# Refi proceeds only happen if new refi loan > acquisition loan payoff
refi_proceeds = max(refi_loan - acq_loan, 0.0)

# Cash left in deal is investor cash still trapped after cash-out
cash_left_in_deal = max(cash_needed_at_close - refi_proceeds, 0.0)

cash_out_multiple = (refi_proceeds / cash_needed_at_close) if cash_needed_at_close > 0 else 0.0

# -----------------------------
# Investor return metrics (simple model)
# -----------------------------
# Year 1 cash flow to equity (NOI - debt service)
year1_cfe = noi - annual_debt
cash_on_cash = (year1_cfe / cash_left_in_deal) if cash_left_in_deal > 0 else 0.0

# Build a simple annual cashflow stream for IRR:
# t0: -cash_needed_at_close
# t1..t(hold_years-1): annual cash flow (growing with NOI growth, debt constant)
# t_hold: annual cash flow + net sale proceeds
cashflows = [-cash_needed_at_close]

noi_t = noi
for _yr in range(1, hold_years):
    year_cfe = (noi_t - annual_debt)
    cashflows.append(year_cfe)
    noi_t = noi_t * (1 + noi_growth)

# Exit sale proceeds in final year
noi_exit = noi_t
sale_price = (noi_exit / exit_cap_sale) if exit_cap_sale > 0 else 0.0
sale_costs = sale_price * sale_cost_pct
net_sale_before_debt = max(sale_price - sale_costs, 0.0)

# Simple assumption: loan payoff equals refi_loan (no amortization tracked here)
loan_payoff = refi_loan
net_sale_proceeds = max(net_sale_before_debt - loan_payoff, 0.0)

final_year_cfe = (noi_exit - annual_debt) + net_sale_proceeds
cashflows.append(final_year_cfe)

irr = safe_irr(cashflows)

total_distributions = sum(cf for cf in cashflows[1:] if cf > 0)
equity_multiple = (total_distributions / cash_needed_at_close) if cash_needed_at_close > 0 else 0.0

# -----------------------------
# Output UI
# -----------------------------
st.subheader("Capital Needed")
st.metric("Cash Needed at Close (All-In)", f"${cash_needed_at_close:,.0f}")

col1, col2, col3 = st.columns(3)
col1.metric("Stabilized NOI", f"${noi:,.0f}")
col1.metric("Stabilized Value", f"${stabilized_value:,.0f}")

col2.metric("Refi Loan", f"${refi_loan:,.0f}")
col2.metric("Annual Debt Service", f"${annual_debt:,.0f}")

col3.metric("DSCR", "—" if np.isnan(dscr) else f"{dscr:.2f}")

st.subheader("Refinance Results")
c4, c5, c6 = st.columns(3)
c4.metric("Refi Proceeds (Cash-Out)", f"${refi_proceeds:,.0f}")
c5.metric("Cash Left in Deal", f"${cash_left_in_deal:,.0f}")
c6.metric("Cash-Out Multiple", f"{cash_out_multiple:.2f}x")

st.subheader("Investor Return Metrics")
r1, r2, r3 = st.columns(3)
r1.metric("Cash-on-Cash (Year 1)", f"{cash_on_cash*100:.2f}%")
r2.metric("IRR (Projected)", "—" if np.isnan(irr) else f"{irr*100:.2f}%")
r3.metric("Equity Multiple", f"{equity_multiple:.2f}x")

with st.expander("Show Assumptions + Cashflows"):
    st.write("**Cashflows (annual):**")
    st.write(cashflows)
    st.write(f"Year 1 CFE: ${year1_cfe:,.0f}")
    st.write(f"Sale Price (Year {hold_years}): ${sale_price:,.0f}")
    st.write(f"Net Sale Proceeds: ${net_sale_proceeds:,.0f}")

