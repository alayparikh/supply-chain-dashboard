import io
import json
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='Supply Chain Cost Dashboard', layout='wide')

DEFAULT_PRODUCTS = pd.DataFrame([
    {'product_id': 1, 'product': 'Wrench', 'weight_lb': 2.2, 'default_supplier': 'A'},
    {'product_id': 2, 'product': 'Saw', 'weight_lb': 1.2, 'default_supplier': 'A'},
    {'product_id': 3, 'product': 'Drill', 'weight_lb': 8.3, 'default_supplier': 'B'},
    {'product_id': 4, 'product': 'Hammer', 'weight_lb': 2.0, 'default_supplier': 'A/B'},
])

DEFAULT_RATES = pd.DataFrame([
    {'carrier': 'X', 'supplier': 'A', 'store': 1, 'flat_rate': 2540.0, 'per_lb_rate': None},
    {'carrier': 'X', 'supplier': 'A', 'store': 2, 'flat_rate': 1640.0, 'per_lb_rate': None},
    {'carrier': 'X', 'supplier': 'B', 'store': 1, 'flat_rate': 1200.0, 'per_lb_rate': None},
    {'carrier': 'X', 'supplier': 'B', 'store': 2, 'flat_rate': 1200.0, 'per_lb_rate': None},
    {'carrier': 'Y', 'supplier': 'A', 'store': 1, 'flat_rate': None, 'per_lb_rate': 0.12},
    {'carrier': 'Y', 'supplier': 'A', 'store': 2, 'flat_rate': None, 'per_lb_rate': 

     DEFAULT_BASE = pd.DataFrame([
    {'week': 'W1', 'store': 1, 'supplier': 'A', 'base_weight_lb': 17105.88, 'wrench_qty': 4771.8},
    {'week': 'W1', 'store': 2, 'supplier': 'A', 'base_weight_lb': 15540.36, 'wrench_qty': 3960.0},
    {'week': 'W2', 'store': 1, 'supplier': 'A', 'base_weight_lb': 18338.32, 'wrench_qty': 5057.8},
    {'week': 'W2', 'store': 2, 'supplier': 'A', 'base_weight_lb': 14489.64, 'wrench_qty': 3557.4},
    {'week': 'W3', 'store': 1, 'supplier': 'A', 'base_weight_lb': 17380.00, 'wrench_qty': 4694.8},
    {'week': 'W3', 'store': 2, 'supplier': 'A', 'base_weight_lb': 12826.22, 'wrench_qty': 2885.3},
    {'week': 'W4', 'store': 1, 'supplier': 'A', 'base_weight_lb': 16428.06, 'wrench_qty': 3798.3},
    {'week': 'W4', 'store': 2, 'supplier': 'A', 'base_weight_lb': 12396.12, 'wrench_qty': 2092.2},
    {'week': 'W1', 'store': 1, 'supplier': 'B', 'base_weight_lb': 17255.70, 'wrench_qty': 4771.8},
    {'week': 'W1', 'store': 2, 'supplier': 'B', 'base_weight_lb': 23153.68, 'wrench_qty': 3960.0},
    {'week': 'W2', 'store': 1, 'supplier': 'B', 'base_weight_lb': 15867.94, 'wrench_qty': 5057.8},
    {'week': 'W2', 'store': 2, 'supplier': 'B', 'base_weight_lb': 18406.08, 'wrench_qty': 3557.4},
    {'week': 'W3', 'store': 1, 'supplier': 'B', 'base_weight_lb': 16269.66, 'wrench_qty': 4694.8},
    {'week': 'W3', 'store': 2, 'supplier': 'B', 'base_weight_lb': 21702.01, 'wrench_qty': 2885.3},
    {'week': 'W4', 'store': 1, 'supplier': 'B', 'base_weight_lb': 22852.39, 'wrench_qty': 3798.3},
    {'week': 'W4', 'store': 2, 'supplier': 'B', 'base_weight_lb': 29952.92, 'wrench_qty': 2092.2},
])


def choose_shipping_cost(total_weight, supplier, store, rates, capacity):
    sub = rates[(rates['supplier'] == supplier) & (rates['store'] == store)]
    flat = sub.loc[sub['carrier'] == 'X', 'flat_rate'].iloc[0]
    var = sub.loc[sub['carrier'] == 'Y', 'per_lb_rate'].iloc[0] * total_weight
    loads = max(1, math.ceil(total_weight / capacity))
    flat_total = flat * loads
    var_total = var
    if flat_total <= var_total:
        return pd.Series({'chosen_carrier': 'X', 'shipping_cost': flat_total, 'shipments': loads})
    return pd.Series({'chosen_carrier': 'Y', 'shipping_cost': var_total, 'shipments': loads})


def run_model(base_df, rates_df, hammer_supplier, hammer_cost_a, hammer_cost_b, growth_pct, hammer_weight, capacity):
    df = base_df.copy()
    df['hammer_qty'] = df['wrench_qty'] * (1 + growth_pct / 100)
    df['hammer_weight_lb'] = df['hammer_qty'] * hammer_weight
    df['total_weight_lb'] = df['base_weight_lb'] + df['hammer_weight_lb']

    modeled = []
    for _, row in df.iterrows():
        supplier = row['supplier']
        if supplier != hammer_supplier:
            row['shipping_cost'] = choose_shipping_cost(row['base_weight_lb'], supplier, row['store'], rates_df, capacity)['shipping_cost']
            row['chosen_carrier'] = choose_shipping_cost(row['base_weight_lb'], supplier, row['store'], rates_df, capacity)['chosen_carrier']
            row['scenario_weight_lb'] = row['base_weight_lb']
            row['hammer_product_cost'] = 0.0
            modeled.append(row)
            continue

        ship = choose_shipping_cost(row['total_weight_lb'], supplier, row['store'], rates_df, capacity)
        row['shipping_cost'] = ship['shipping_cost']
        row['chosen_carrier'] = ship['chosen_carrier']
        row['scenario_weight_lb'] = row['total_weight_lb']
        unit_cost = hammer_cost_a if hammer_supplier == 'A' else hammer_cost_b
        row['hammer_product_cost'] = row['hammer_qty'] * unit_cost
        modeled.append(row)

    out = pd.DataFrame(modeled)
    weekly = out.groupby(['week', 'store', 'supplier'], as_index=False).agg(
        scenario_weight_lb=('scenario_weight_lb', 'sum'),
        hammer_qty=('hammer_qty', 'sum'),
        hammer_weight_lb=('hammer_weight_lb', 'sum'),
        shipping_cost=('shipping_cost', 'sum'),
        hammer_product_cost=('hammer_product_cost', 'sum')
    )
    weekly['total_cost'] = weekly['shipping_cost'] + weekly['hammer_product_cost']

    supplier_summary = weekly.groupby('supplier', as_index=False).agg(
        annual_shipping_cost=('shipping_cost', 'sum'),
        annual_hammer_product_cost=('hammer_product_cost', 'sum')
    )
    supplier_summary['annual_total_cost'] = supplier_summary['annual_shipping_cost'] + supplier_summary['annual_hammer_product_cost']
    supplier_summary['scenario_role'] = supplier_summary['supplier'].apply(
        lambda s: 'Chosen hammer supplier' if s == hammer_supplier else 'Existing network only'
    )
    return weekly, supplier_summary


st.title('Supply Chain Supplier Cost Dashboard')
st.caption('Editable, free MVP for supplier + shipping scenario analysis')

with st.sidebar:
    st.header('Scenario controls')
    hammer_supplier = st.radio('Hammer supplier', ['A', 'B'], horizontal=True)
    growth_pct = st.number_input('YoY growth %', value=10.0, step=1.0)
    hammer_cost_a = st.number_input('Hammer cost - Supplier A ($/unit)', value=0.80, step=0.01, format='%.2f')
    hammer_cost_b = st.number_input('Hammer cost - Supplier B ($/unit)', value=0.82, step=0.01, format='%.2f')
    hammer_weight = st.number_input('Hammer weight (lb)', value=2.0, step=0.1)
    capacity = st.number_input('Truck capacity (lb)', value=44000, step=1000)
    st.markdown('---')
    upload = st.file_uploader('Optional: upload weekly base data CSV', type=['csv'])

st.subheader('Editable master data')
col1, col2 = st.columns([1, 1])

with col1:
    products = st.data_editor(DEFAULT_PRODUCTS, num_rows='dynamic', use_container_width=True)

with col2:
    rates = st.data_editor(DEFAULT_RATES, num_rows='dynamic', use_container_width=True)

st.subheader('Weekly shipment base')
base_df = DEFAULT_BASE if upload is None else pd.read_csv(upload)
base_df = st.data_editor(base_df, num_rows='dynamic', use_container_width=True)

weekly, summary = run_model(
    base_df,
    rates,
    hammer_supplier,
    hammer_cost_a,
    hammer_cost_b,
    growth_pct,
    hammer_weight,
    capacity
)

chosen_total = float(summary.loc[summary['supplier'] == hammer_supplier, 'annual_total_cost'].sum())
other_supplier = 'B' if hammer_supplier == 'A' else 'A'
other_total = float(summary.loc[summary['supplier'] == other_supplier, 'annual_total_cost'].sum())
delta = chosen_total - other_total

m1, m2, m3 = st.columns(3)
m1.metric('Chosen supplier total cost', f'${chosen_total:,.0f}')
m2.metric('Other supplier total cost', f'${other_total:,.0f}')
m3.metric('Cost gap', f'${abs(delta):,.0f}', delta=('Lower cost' if delta < 0 else 'Higher cost'))

chart_df = summary.copy()
fig = px.bar(
    chart_df,
    x='supplier',
    y='annual_total_cost',
    color='supplier',
    text_auto='.2s',
    title='Annual total cost by supplier network'
)
fig.update_layout(showlegend=False, height=420)
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns([1.2, 1])

with c1:
    st.subheader('Supplier totals')
    st.dataframe(summary, use_container_width=True)

with c2:
    st.subheader('Weekly detail')
    st.dataframe(weekly, use_container_width=True, height=420)

export_summary = summary.to_csv(index=False).encode('utf-8')
export_weekly = weekly.to_csv(index=False).encode('utf-8')

x1, x2 = st.columns(2)
x1.download_button(
    'Download supplier summary CSV',
    export_summary,
    file_name='supplier_summary.csv',
    mime='text/csv'
)
x2.download_button(
    'Download weekly detail CSV',
    export_weekly,
    file_name='weekly_detail.csv',
    mime='text/csv'
)

with st.expander('Implementation notes / next steps'):
    st.markdown('''
- Replace the sample weekly base table with a parser for the attached Excel workbook.
- Add authentication if you want named users and saved scenarios.
- Add scenario save/load using SQLite or JSON.
- Add store-level recommendation cards and sensitivity analysis.
- Deploy free on Streamlit Community Cloud from GitHub.
''')
