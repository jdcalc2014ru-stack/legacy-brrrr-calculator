import streamlit as st

st.set_page_config(page_title="Legacy BRRRR Calculator", layout="wide")

st.title("🏢 Legacy Multifamily BRRRR Calculator")

st.sidebar.header("Acquisition")

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

# Calculations

gross_rent = units * rent * 12
effective_income = gross_rent * (1 - vacancy)

expenses = effective_income * 0.40  # assume 40% expense ratio
noi = effective_income - expenses

stabilized_value = noi / exit_cap
refi_loan = stabilized_value * refi_ltv

import numpy as np

def pmt(rate, nper, pv):
    if rate == 0:
        return pv / nper
    return (rate * pv) / (1 - (1 + rate) ** (-nper))

annual_debt = pmt(refi_rate, amort_years, refi_loan)
dscr = noi / annual_debt

# Output

col1, col2, col3 = st.columns(3)

col1.metric("Stabilized NOI", f"${noi:,.0f}")
col1.metric("Stabilized Value", f"${stabilized_value:,.0f}")

col2.metric("Refi Loan", f"${refi_loan:,.0f}")
col2.metric("Annual Debt Service", f"${annual_debt:,.0f}")

col3.metric("DSCR", f"{dscr:.2f}")
