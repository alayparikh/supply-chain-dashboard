import copy
import streamlit as st
from data_loader import load_workbook_data, build_defaults_from_workbook
from logic import build_summary, scenario_is_modified

st.set_page_config(page_title="Supply Chain Dashboard", layout="wide")

DEFAULT_WORKBOOK_PATH = "CaseStudy_Analyst_Final.xlsx"

@st.cache_data
def get_workbook_data(source_name: str, file_bytes: bytes | None = None):
    if file_bytes is not None:
        import io
        return load_workbook_data(io.BytesIO(file_bytes))
    return load_workbook_data(source_name)

with st.sidebar:
    st.header("Workbook")
    uploaded_file = st.file_uploader("Upload case study workbook", type=["xlsx"])
    source_label = uploaded_file.name if uploaded_file else DEFAULT_WORKBOOK_PATH

if uploaded_file:
    workbook_data = get_workbook_data(uploaded_file.name, uploaded_file.getvalue())
else:
    workbook_data = get_workbook_data(DEFAULT_WORKBOOK_PATH)

workbook_defaults = build_defaults_from_workbook(workbook_data)

if st.session_state.get("active_workbook") != source_label:
    st.session_state.active_workbook = source_label
    st.session_state.workbook_defaults = copy.deepcopy(workbook_defaults)
    st.session_state.scenario_growth_factor = float(workbook_defaults["growth_factor"])
    st.session_state.scenario_hammer_weight = float(workbook_defaults["hammer_weight"])
    st.session_state.scenario_hammer_cost_a = float(workbook_defaults["hammer_costs"]["A"])
    st.session_state.scenario_hammer_cost_b = float(workbook_defaults["hammer_costs"]["B"])
    st.session_state.scenario_product_info = workbook_defaults["product_info"].copy()
    st.session_state.scenario_carrier_rates = workbook_defaults["carrier_rates"].copy()

st.title("Supply Chain Supplier Cost Dashboard")
st.caption("Defaults load from the workbook and can be edited in the UI")

with st.sidebar:
    st.header("Scenario Controls")

    if st.button("Reset to workbook defaults", use_container_width=True):
        st.session_state.scenario_growth_factor = float(st.session_state.workbook_defaults["growth_factor"])
        st.session_state.scenario_hammer_weight = float(st.session_state.workbook_defaults["hammer_weight"])
        st.session_state.scenario_hammer_cost_a = float(st.session_state.workbook_defaults["hammer_costs"]["A"])
        st.session_state.scenario_hammer_cost_b = float(st.session_state.workbook_defaults["hammer_costs"]["B"])
        st.session_state.scenario_product_info = st.session_state.workbook_defaults["product_info"].copy()
        st.session_state.scenario_carrier_rates = st.session_state.workbook_defaults["carrier_rates"].copy()
        st.rerun()

    st.session_state.scenario_growth_factor = st.number_input(
        "Growth factor", min_value=1.0,
        value=st.session_state.scenario_growth_factor,
        step=0.01, format="%.2f"
    )
    st.session_state.scenario_hammer_weight = st.number_input(
        "Hammer unit weight (lb)", min_value=0.0,
        value=st.session_state.scenario_hammer_weight,
        step=0.1, format="%.1f"
    )
    st.session_state.scenario_hammer_cost_a = st.number_input(
        "Hammer cost Supplier A", min_value=0.0,
        value=st.session_state.scenario_hammer_cost_a,
        step=0.01, format="%.2f"
    )
    st.session_state.scenario_hammer_cost_b = st.number_input(
        "Hammer cost Supplier B", min_value=0.0,
        value=st.session_state.scenario_hammer_cost_b,
        step=0.01, format="%.2f"
    )

scenario = {
    "growth_factor": st.session_state.scenario_growth_factor,
    "hammer_weight": st.session_state.scenario_hammer_weight,
    "hammer_costs": {
        "A": st.session_state.scenario_hammer_cost_a,
        "B": st.session_state.scenario_hammer_cost_b,
    },
    "product_info": st.session_state.scenario_product_info.copy(),
    "carrier_rates": st.session_state.scenario_carrier_rates.copy(),
}

modified = scenario_is_modified(scenario, st.session_state.workbook_defaults)
st.info("Edited scenario" if modified else "Workbook defaults active")

summary_df, supplier_a_df, supplier_b_df, parity_df = build_summary(workbook_data, scenario)

summary_tab, inputs_tab, a_tab, b_tab, parity_tab = st.tabs(
    ["Summary", "Inputs", "Supplier A Detail", "Supplier B Detail", "Workbook Parity Check"]
)

with summary_tab:
    a_total = float(summary_df.loc[summary_df["Supplier"] == "A", "Total Annual Cost"].iloc[0])
    b_total = float(summary_df.loc[summary_df["Supplier"] == "B", "Total Annual Cost"].iloc[0])
    recommended = "A" if a_total < b_total else "B"
    savings = abs(a_total - b_total)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Supplier A total", f"${a_total:,.0f}")
    c2.metric("Supplier B total", f"${b_total:,.0f}")
    c3.metric("Recommended supplier", recommended)
    c4.metric("Annual savings", f"${savings:,.0f}")

    st.subheader("Annual Summary")
    st.dataframe(summary_df, use_container_width=True)
    st.download_button(
        "Download summary CSV",
        summary_df.to_csv(index=False).encode("utf-8"),
        file_name="supplier_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )

with inputs_tab:
    st.subheader("Carrier Rates")
    st.session_state.scenario_carrier_rates = st.data_editor(
        st.session_state.scenario_carrier_rates,
        num_rows="fixed",
        use_container_width=True,
        key="carrier_rates_editor",
    ).copy()

    st.subheader("Product Weights")
    st.session_state.scenario_product_info = st.data_editor(
        st.session_state.scenario_product_info,
        num_rows="fixed",
        use_container_width=True,
        key="product_info_editor",
    ).copy()

with a_tab:
    st.subheader("Supplier A Weekly Detail")
    st.dataframe(supplier_a_df, use_container_width=True)
    st.download_button(
        "Download Supplier A CSV",
        supplier_a_df.to_csv(index=False).encode("utf-8"),
        file_name="supplier_a_detail.csv",
        mime="text/csv",
        use_container_width=True,
    )

with b_tab:
    st.subheader("Supplier B Weekly Detail")
    st.dataframe(supplier_b_df, use_container_width=True)
    st.download_button(
        "Download Supplier B CSV",
        supplier_b_df.to_csv(index=False).encode("utf-8"),
        file_name="supplier_b_detail.csv",
        mime="text/csv",
        use_container_width=True,
    )

with parity_tab:
    st.subheader("Workbook Parity Check")
    st.caption("Difference should be close to zero when workbook defaults are active")
    st.dataframe(parity_df, use_container_width=True)