import streamlit as st
import numpy as np
import numpy_financial as npf

st.set_page_config(page_title="Legacy BRRRR Calculator", layout="wide")

st.title("🏢 Legacy Family Fund BRRRR Calculator")

st.sidebar.header("Acquisition")

st.sidebar.subheader("Closing & Reserves")
closing_cost_pct = st.sidebar.number_input("Closing Costs (% of Purchase)", value=2.0, step=0.25) / 100
lender_fees_pct = st.sidebar.number_input("Lender Fees (% of Loan)", value=1.0, step=0.25) / 100
initial_reserves = st.sidebar.number_input("Initial Reserves ($)", value=25000.0, step=5000.0)

purchase_price = st.sidebar.number_input("Purchase Price ($)", value=6000000.0, step=50000.0)
units = st.sidebar.number_input("Units", value=24)
rent = st.sidebar.number_input("Market Rent per Unit ($/month)", value=1650.0)
vacancy = st.sidebar.number_input("Vacancy (%)", value=7.0) / 100

st.sidebar.header("Rehab")

st.sidebar.subheader("Rehab Timing")
rehab_months = st.sidebar.number_input("Rehab Months", value=6, step=1)
rehab_per_unit = st.sidebar.number_input("Rehab per Unit ($)", value=15000.0)
exterior_rehab = st.sidebar.number_input("Exterior Rehab ($)", value=80000.0)

st.sidebar.header("Refi")

st.sidebar.header("Investor Returns")

hold_years = st.sidebar.number_input("Hold Period (Years)", value=5, step=1, min_value=1)
rent_growth = st.sidebar.number_input("Annual Rent/NOI Growth (%)", value=3.0, step=0.25) / 100
sale_cost_pct = st.sidebar.number_input("Sale Costs (% of Sale Price)", value=3.0, step=0.25) / 100

exit_cap_sale = st.sidebar.number_input("Exit Cap at Sale (%)", value=6.5, step=0.25) / 100

exit_cap = st.sidebar.number_input("Exit Cap Rate (%)", value=6.5) / 100
refi_ltv = st.sidebar.number_input("Refi LTV (%)", value=75.0) / 100
refi_rate = st.sidebar.number_input("Refi Rate (%)", value=7.25) / 100
amort_years = st.sidebar.number_input("Amortization (Years)", value=30)


# Calculations


# --- Cash Needed at Close ---
total_rehab = rehab_per_unit * units + exterior_rehab

purchase_closing_costs = purchase_price * closing_cost_pct

# Estimate acquisition loan amount (interest-only or bridge assumption)
acq_ltv = st.sidebar.number_input("Acquisition LTV (%)", value=80.0, step=1.0) / 100
acq_loan = purchase_price * acq_ltv
down_payment = purchase_price - acq_loan

lender_fees = acq_loan * lender_fees_pct

cash_needed_at_close = down_payment + purchase_closing_costs + lender_fees + total_rehab + initial_reserves
gross_rent = units * rent * 12
effective_income = gross_rent * (1 - vacancy)

expenses = effective_income * 0.40  # assume 40% expense ratio
noi = effective_income - expenses

stabilized_value = noi / exit_cap
refi_loan = stabilized_value * refi_ltv

# --- Refinance Proceeds ---
all_in_cost = purchase_price + purchase_closing_costs + lender_fees + total_rehab+initial_reserves

# Refi pays off acquisition loan
refi_proceeds = max(refi_loan - acq_loan, 0)

cash_left_in_deal = max(all_in_cost - refi_proceeds, 0)

cash_out_multiple = (refi_proceeds / cash_needed_at_close) if cash_needed_at_close > 0 else 0


def pmt(rate, nper, pv):
    if rate == 0:
        return pv / nper
    return (rate * pv) / (1 - (1 + rate) ** (-nper))

annual_debt = pmt(refi_rate, amort_years, refi_loan)

# ---- Investor Returns ----
equity_invested = cash_left_in_deal  # equity still in deal after cash-out

# Year 1 cash flow to equity (simple)
year1_cfe = noi - annual_debt

# Build cash flows for IRR (annual)
cashflows = []
cashflows.append(-equity_invested)

# Project NOI growth each year (expense ratio stays constant in your model)
for y in range(1, hold_years + 1):
    noi_y = noi * ((1 + rent_growth) ** (y - 1))
    cfe_y = noi_y - annual_debt

    # Final year includes sale proceeds
    if y == hold_years:
        noi_sale = noi * ((1 + rent_growth) ** (hold_years - 1))
        sale_price = noi_sale / exit_cap_sale
        sale_net = sale_price * (1 - sale_cost_pct)

        # Remaining loan balance after hold_years (annual amort)
        # annual_debt is the annual payment from your pmt()
        if refi_rate == 0:
            remaining_balance = max(refi_loan - (refi_loan / amort_years) * hold_years, 0)
        else:
            remaining_balance = refi_loan * ((1 + refi_rate) ** hold_years) - annual_debt * (((1 + refi_rate) ** hold_years - 1) / refi_rate)

        sale_proceeds = max(sale_net - remaining_balance, 0)
        cfe_y += sale_proceeds

    cashflows.append(cfe_y)

# Cash-on-cash (Year 1)
cash_on_cash = (year1_cfe / equity_invested) if equity_invested > 0 else 0

# IRR + Equity Multiple
irr = npf.irr(cashflows) if len(cashflows) > 1 else 0
total_distributions = sum([cf for cf in cashflows if cf > 0])
equity_multiple = (total_distributions / equity_invested) if equity_invested > 0 else 0


dscr = noi / annual_debt

# Output

st.subheader("Capital Needed")
st.metric("Cash Needed at Close (All-In)", f"${cash_needed_at_close:,.0f}")

col1, col2, col3 = st.columns(3)
col1.metric("Stabilized NOI", f"${noi:,.0f}")
col1.metric("Stabilized Value", f"${stabilized_value:,.0f}")

col2.metric("Refi Loan", f"${refi_loan:,.0f}")
col2.metric("Annual Debt Service", f"${annual_debt:,.0f}")

col3.metric("DSCR", f"{dscr:.2f}")
st.subheader("Refinance Results")

st.subheader("Investor Return Metrics")

r1, r2, r3 = st.columns(3)
r1.metric("Cash-on-Cash (Year 1)", f"{cash_on_cash*100:.2f}%")
r2.metric("IRR (Projected)", f"{irr*100:.2f}%")
r3.metric("Equity Multiple", f"{equity_multiple:.2f}x")

col4, col5, col6 = st.columns(3)

col4.metric("Refi Proceeds (Cash-Out)", f"${refi_proceeds:,.0f}")
col5.metric("Cash Left In Deal", f"${cash_left_in_deal:,.0f}")
col6.metric("Cash-Out Multiple", f"{cash_out_multiple:.2f}x")