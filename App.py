import streamlit as st
import numpy as np
import numpy_financial as npf

st.set_page_config(page_title="Legacy BRRRR Calculator", layout="wide")

st.title("🏢 Legacy Family Fund BRRRR Calculator")

# --------------------------
# SIDEBAR INPUTS
# --------------------------

st.sidebar.header("Acquisition")

closing_cost_pct = st.sidebar.number_input("Closing Costs (% of Purchase)", value=2.0, step=0.25) / 100
lender_fees_pct = st.sidebar.number_input("Lender Fees (% of Loan)", value=1.0, step=0.25) / 100
initial_reserves = st.sidebar.number_input("Initial Reserves ($)", value=25000.0, step=5000.0)

purchase_price = st.sidebar.number_input("Purchase Price ($)", value=6000000.0, step=50000.0)
units = st.sidebar.number_input("Units", value=24)
rent = st.sidebar.number_input("Market Rent per Unit ($/month)", value=1650.0)
vacancy = st.sidebar.number_input("Vacancy (%)", value=7.0) / 100

st.sidebar.header("Rehab")
rehab_per_unit = st.sidebar.number_input("Rehab per Unit ($)", value=15000.0)
exterior_rehab = st.sidebar.number_input("Exterior Rehab ($)", value=80000.0)

st.sidebar.header("Refi")

exit_cap = st.sidebar.number_input("Exit Cap Rate (%)", value=6.5) / 100
refi_ltv = st.sidebar.number_input("Refi LTV (%)", value=75.0) / 100
refi_rate = st.sidebar.number_input("Refi Rate (%)", value=7.25) / 100
amort_years = st.sidebar.number_input("Amortization (Years)", value=30)

acq_ltv = st.sidebar.number_input("Acquisition LTV (%)", value=80.0) / 100

hold_years = st.sidebar.number_input("Hold Period (Years)", value=5)

# --------------------------
# CALCULATIONS
# --------------------------

total_rehab = rehab_per_unit * units + exterior_rehab
purchase_closing_costs = purchase_price * closing_cost_pct

acq_loan = purchase_price * acq_ltv
down_payment = purchase_price - acq_loan
lender_fees = acq_loan * lender_fees_pct

cash_needed_at_close = (
    down_payment + purchase_closing_costs + lender_fees + total_rehab + initial_reserves
)

gross_rent = units * rent * 12
effective_income = gross_rent * (1 - vacancy)

expenses = effective_income * 0.40
noi = effective_income - expenses

stabilized_value = noi / exit_cap
refi_loan = stabilized_value * refi_ltv

# Refinance math
all_in_cost = purchase_price + purchase_closing_costs + lender_fees + total_rehab + initial_reserves
refi_proceeds = max(refi_loan - acq_loan, 0)
cash_left_in_deal = max(all_in_cost - refi_proceeds, 0)
cash_out_multiple = (refi_proceeds / cash_needed_at_close) if cash_needed_at_close > 0 else 0

# Debt service
def pmt(rate, nper, pv):
    if rate == 0:
        return pv / nper
    return (rate * pv) / (1 - (1 + rate) ** (-nper))

annual_debt = pmt(refi_rate, amort_years, refi_loan)
dscr = noi / annual_debt if annual_debt > 0 else 0

# --------------------------
# INVESTOR RETURNS
# --------------------------

equity_invested = cash_left_in_deal
year1_cfe = noi - annual_debt

cash_on_cash = year1_cfe / equity_invested if equity_invested > 0 else 0

# Projected sale
exit_cap_sale = exit_cap
sale_value = noi / exit_cap_sale
loan_balance = refi_loan  # simplified (no amortization tracking)

sale_proceeds = sale_value - loan_balance

cashflows = [-equity_invested] + [year1_cfe] * hold_years
cashflows[-1] += sale_proceeds

irr = npf.irr(cashflows) if len(cashflows) > 1 else 0

total_distributions = sum([cf for cf in cashflows if cf > 0])
equity_multiple = total_distributions / equity_invested if equity_invested > 0 else 0

# --------------------------
# OUTPUT
# --------------------------

st.subheader("Capital Needed")
st.metric("Cash Needed at Close (All-In)", f"${cash_needed_at_close:,.0f}")

col1, col2, col3 = st.columns(3)

col1.metric("Stabilized NOI", f"${noi:,.0f}")
col1.metric("Stabilized Value", f"${stabilized_value:,.0f}")

col2.metric("Refi Loan", f"${refi_loan:,.0f}")
col2.metric("Annual Debt Service", f"${annual_debt:,.0f}")

col3.metric("DSCR", f"{dscr:.2f}")

# Refinance
st.subheader("Refinance Results")

c1, c2, c3 = st.columns(3)

c1.metric("Refi Proceeds (Cash-Out)", f"${refi_proceeds:,.0f}")
c2.metric("Cash Left In Deal", f"${cash_left_in_deal:,.0f}")
c3.metric("Cash-Out Multiple", f"{cash_out_multiple:.2f}x")

# Investor Returns
st.subheader("Investor Return Metrics")

r1, r2, r3 = st.columns(3)

r1.metric("Cash-on-Cash (Year 1)", f"{cash_on_cash*100:.2f}%")
r2.metric("IRR (Projected)", f"{irr*100:.2f}%")
r3.metric("Equity Multiple", f"{equity_multiple:.2f}x")

