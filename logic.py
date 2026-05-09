import pandas as pd


def _carrier_cost(x_rate: float, y_rate: float, weight: float) -> tuple[float, str]:
    x_cost = x_rate
    y_cost = y_rate * weight
    if x_cost <= y_cost:
        return x_cost, "X (Flat)"
    return y_cost, "Y (Variable)"


def _carrier_rates_for(carrier_df: pd.DataFrame, supplier: str, store: int) -> tuple[float, float]:
    x = carrier_df[
        (carrier_df["Carrier"] == "X") &
        (carrier_df["Supplier"] == supplier) &
        (carrier_df["Str Nbr"] == store)
    ]["Cost"]
    y = carrier_df[
        (carrier_df["Carrier"] == "Y") &
        (carrier_df["Supplier"] == supplier) &
        (carrier_df["Str Nbr"] == store)
    ]["Cost"]
    return float(x.iloc[0]), float(y.iloc[0])


def build_supplier_detail(workbook_data: dict, scenario: dict, hammer_supplier: str) -> pd.DataFrame:
    """
    Weekly detail table for one supplier when that supplier ships hammers.
    Columns include 'with hammers' costs and 'base only' costs (without hammers).
    """
    carrier_df = scenario["carrier_rates"]
    hist_ship = workbook_data["historical_shipments"]
    weekly_demand = workbook_data["weekly_hammer_demand"]

    growth = float(scenario["growth_factor"])
    h_weight = float(scenario["hammer_weight"])
    h_price = float(scenario["hammer_costs"][hammer_supplier])

    # Demand rows are recorded under Supplier A (wrench orders drive hammer forecast)
    demand = weekly_demand[weekly_demand["Supplier"] == "A"].copy()

    rows = []
    for _, dr in demand.iterrows():
        order_week = pd.Timestamp(dr["Order Dt"])
        store = int(dr["Str Nbr"])
        wrench_qty = float(dr["Order Qty (Wrench)"])

        hammer_qty = wrench_qty * growth
        hammer_wt = hammer_qty * h_weight

        week_str = order_week.strftime("%Y-%m-%d")
        key = f"{week_str}-{store}-{hammer_supplier}"
        match = hist_ship[hist_ship["Key"] == key]
        if match.empty:
            continue

        base_wt_2014 = float(match["Weight(2014 total weight)"].iloc[0])
        projected_base_wt = base_wt_2014 * growth
        total_wt = projected_base_wt + hammer_wt

        x_rate, y_rate = _carrier_rates_for(carrier_df, hammer_supplier, store)

        shipping_with, carrier_with = _carrier_cost(x_rate, y_rate, total_wt)
        shipping_base, carrier_base = _carrier_cost(x_rate, y_rate, projected_base_wt)

        rows.append({
            "Order Week": order_week,
            "Store": store,
            "Wrench Qty": int(wrench_qty),
            "Hammer Qty Forecast": round(hammer_qty, 1),
            "Hammer Shipment Weight (lb)": round(hammer_wt, 2),
            "Base Weight 2014 (lb)": base_wt_2014,
            "Projected Base Weight 2015 (lb)": round(projected_base_wt, 2),
            "Total Weight With Hammers (lb)": round(total_wt, 2),
            "Carrier X Rate ($)": x_rate,
            "Carrier Y Rate ($/lb)": y_rate,
            "Carrier X Cost": x_rate,
            "Carrier Y Cost (With Hammers)": round(y_rate * total_wt, 4),
            "Carrier Selected": carrier_with,
            "Weekly Shipping Cost": round(shipping_with, 4),
            "Carrier Y Cost (Base Only)": round(y_rate * projected_base_wt, 4),
            "Carrier Selected (Base)": carrier_base,
            "Weekly Shipping Cost (Base Only)": round(shipping_base, 4),
            "Hammer Product Cost ($)": round(hammer_qty * h_price, 3),
        })

    return pd.DataFrame(rows)


def build_summary(workbook_data: dict, scenario: dict):
    df_a = build_supplier_detail(workbook_data, scenario, "A")
    df_b = build_supplier_detail(workbook_data, scenario, "B")

    total_hammer_demand = df_a["Hammer Qty Forecast"].sum()

    hammer_prod_cost_a = df_a["Hammer Product Cost ($)"].sum()
    hammer_prod_cost_b = df_b["Hammer Product Cost ($)"].sum()

    transport_a_with = df_a["Weekly Shipping Cost"].sum()
    transport_b_with = df_b["Weekly Shipping Cost"].sum()
    transport_a_base = df_a["Weekly Shipping Cost (Base Only)"].sum()
    transport_b_base = df_b["Weekly Shipping Cost (Base Only)"].sum()

    # Scenario A: A ships hammers → A pays with-hammer rates, B stays at base
    total_transport_a = transport_a_with + transport_b_base
    total_cost_a = hammer_prod_cost_a + total_transport_a

    # Scenario B: B ships hammers → B pays with-hammer rates, A stays at base
    total_transport_b = transport_b_with + transport_a_base
    total_cost_b = hammer_prod_cost_b + total_transport_b

    # Hammer-only view (just this supplier's costs: product + their own shipping)
    hammer_only_a = hammer_prod_cost_a + transport_a_with
    hammer_only_b = hammer_prod_cost_b + transport_b_with

    summary = {
        "total_hammer_demand": total_hammer_demand,
        "hammer_price_a": scenario["hammer_costs"]["A"],
        "hammer_price_b": scenario["hammer_costs"]["B"],
        "hammer_prod_cost_a": hammer_prod_cost_a,
        "hammer_prod_cost_b": hammer_prod_cost_b,
        "transport_a_with": transport_a_with,
        "transport_b_with": transport_b_with,
        "transport_a_base": transport_a_base,
        "transport_b_base": transport_b_base,
        "total_transport_a": total_transport_a,
        "total_transport_b": total_transport_b,
        "hammer_only_a": hammer_only_a,
        "hammer_only_b": hammer_only_b,
        "total_cost_a": total_cost_a,
        "total_cost_b": total_cost_b,
    }

    return summary, df_a, df_b


def scenario_is_modified(scenario: dict, defaults: dict) -> bool:
    if abs(scenario["growth_factor"] - defaults["growth_factor"]) > 1e-9:
        return True
    if abs(scenario["hammer_weight"] - defaults["hammer_weight"]) > 1e-9:
        return True
    for sup in ("A", "B"):
        if abs(scenario["hammer_costs"][sup] - defaults["hammer_costs"][sup]) > 1e-9:
            return True
    return False
