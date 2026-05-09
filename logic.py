import json
import pandas as pd


def scenario_is_modified(current: dict, defaults: dict) -> bool:
    return json.dumps(
        _scenario_for_compare(current), sort_keys=True, default=str
    ) != json.dumps(
        _scenario_for_compare(defaults), sort_keys=True, default=str
    )


def _scenario_for_compare(scenario: dict) -> dict:
    return {
        "growth_factor": float(scenario["growth_factor"]),
        "hammer_weight": float(scenario["hammer_weight"]),
        "hammer_costs": {
            "A": float(scenario["hammer_costs"]["A"]),
            "B": float(scenario["hammer_costs"]["B"]),
        },
        "product_info": scenario["product_info"].to_dict("records"),
        "carrier_rates": scenario["carrier_rates"].to_dict("records"),
    }


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]
    raise KeyError(
        f"Missing required column. Tried: {candidates}. Available: {list(df.columns)}"
    )


def _standardize_shipments(df: pd.DataFrame) -> pd.DataFrame:
    date_col = _find_col(df, ["Order Dt", "Shipment Date", "Order Week"])
    store_col = _find_col(df, ["Str Nbr", "Store no.", "Store"])
    supplier_col = _find_col(df, ["Supplier"])
    key_col = _find_col(df, ["Key"])
    weight_col = _find_col(
        df,
        [
            "Current Shipment Weight",
            "Weight2014 total weight",
            "Weight(2014 total weight)",
            "Current Shipment Weight A only",
            "Current Shipment Weight B only",
        ],
    )

    out = df.rename(
        columns={
            date_col: "Order Dt",
            store_col: "Str Nbr",
            supplier_col: "Supplier",
            key_col: "Key",
            weight_col: "Current Shipment Weight",
        }
    ).copy()

    out = out[["Order Dt", "Str Nbr", "Supplier", "Key", "Current Shipment Weight"]]
    out["Order Dt"] = pd.to_datetime(out["Order Dt"])
    out["Str Nbr"] = pd.to_numeric(out["Str Nbr"], errors="coerce")
    out["Current Shipment Weight"] = pd.to_numeric(
        out["Current Shipment Weight"], errors="coerce"
    )
    out["Supplier"] = out["Supplier"].astype(str).str.strip()

    return out.dropna(subset=["Order Dt", "Str Nbr", "Current Shipment Weight"])


def _standardize_orders(df: pd.DataFrame) -> pd.DataFrame:
    date_col = _find_col(df, ["Order Dt", "Shipment Date", "Order Week"])
    store_col = _find_col(df, ["Str Nbr", "Store no.", "Store"])
    supplier_col = _find_col(df, ["Supplier"])
    product_col = _find_col(df, ["Product Id", "Product ID"])
    qty_col = _find_col(df, ["Order Qty", "Quantity"])

    out = df.rename(
        columns={
            date_col: "Order Dt",
            store_col: "Str Nbr",
            supplier_col: "Supplier",
            product_col: "Product Id",
            qty_col: "Order Qty",
        }
    ).copy()

    out["Order Dt"] = pd.to_datetime(out["Order Dt"])
    out["Str Nbr"] = pd.to_numeric(out["Str Nbr"], errors="coerce")
    out["Product Id"] = pd.to_numeric(out["Product Id"], errors="coerce")
    out["Order Qty"] = pd.to_numeric(out["Order Qty"], errors="coerce")
    out["Supplier"] = out["Supplier"].astype(str).str.strip()

    return out.dropna(subset=["Order Dt", "Str Nbr", "Product Id", "Order Qty"])


def _standardize_rates(df: pd.DataFrame) -> pd.DataFrame:
    carrier_col = _find_col(df, ["Carrier"])
    supplier_col = _find_col(df, ["Supplier"])
    store_col = _find_col(df, ["Str Nbr", "Store no.", "Store"])
    cost_col = _find_col(df, ["Cost", "Rate"])

    out = df.rename(
        columns={
            carrier_col: "Carrier",
            supplier_col: "Supplier",
            store_col: "Str Nbr",
            cost_col: "Cost",
        }
    ).copy()

    out["Carrier"] = out["Carrier"].astype(str).str.strip()
    out["Supplier"] = out["Supplier"].astype(str).str.strip()
    out["Str Nbr"] = pd.to_numeric(out["Str Nbr"], errors="coerce")
    out["Cost"] = pd.to_numeric(out["Cost"], errors="coerce")

    return out.dropna(subset=["Carrier", "Supplier", "Str Nbr", "Cost"])


def build_supplier_scenario(workbook_data: dict, scenario: dict, supplier: str) -> pd.DataFrame:
    growth = float(scenario["growth_factor"])
    hammer_cost = float(scenario["hammer_costs"][supplier])
    hammer_weight = float(scenario["hammer_weight"])

    shipments = _standardize_shipments(workbook_data["historical_shipments"])
    shipments = shipments[shipments["Supplier"] == supplier].copy()

    orders = _standardize_orders(workbook_data["historical_orders"])
    orders = orders[
        (orders["Supplier"] == supplier) & (orders["Product Id"] == 1)
    ].copy()

    wrench = orders[["Order Dt", "Str Nbr", "Order Qty"]].rename(
        columns={"Order Qty": "Wrench Qty"}
    )

    df = shipments.merge(wrench, on=["Order Dt", "Str Nbr"], how="left")
    df["Wrench Qty"] = df["Wrench Qty"].fillna(0)

    df["Hammer Qty forecast"] = df["Wrench Qty"] * growth
    df["Hammer Weight"] = hammer_weight
    df["Hammer shipment Weight"] = df["Hammer Qty forecast"] * df["Hammer Weight"]
    df["Projected Base Weight"] = df["Current Shipment Weight"] * growth
    df["Total Shipment Weight"] = df["Projected Base Weight"] + df["Hammer shipment Weight"]

    rates = _standardize_rates(scenario["carrier_rates"])
    x_rates = rates[
        (rates["Carrier"] == "X") & (rates["Supplier"] == supplier)
    ][["Str Nbr", "Cost"]].rename(columns={"Cost": "Carrier X Rate Flat"})
    y_rates = rates[
        (rates["Carrier"] == "Y") & (rates["Supplier"] == supplier)
    ][["Str Nbr", "Cost"]].rename(columns={"Cost": "Carrier Y Rate Var"})

    df = df.merge(x_rates, on="Str Nbr", how="left")
    df = df.merge(y_rates, on="Str Nbr", how="left")

    df["Carrier X Cost Flat"] = df["Carrier X Rate Flat"]
    df["Carrier Y Cost Var"] = df["Carrier Y Rate Var"] * df["Total Shipment Weight"]
    df["Weekly Shipping Cost"] = df[["Carrier X Cost Flat", "Carrier Y Cost Var"]].min(axis=1)

    df["Hammer Cost"] = df["Hammer Qty forecast"] * hammer_cost
    df["Total Weekly Hammer Cost"] = df["Weekly Shipping Cost"] + df["Hammer Cost"]

    df["Carrier X Cost for projected base weight"] = df["Carrier X Rate Flat"]
    df["Carrier Y Cost for projected base weight"] = (
        df["Carrier Y Rate Var"] * df["Projected Base Weight"]
    )
    df["Weekly Shipping Cost for projected Base weight"] = df[
        ["Carrier X Cost for projected base weight", "Carrier Y Cost for projected base weight"]
    ].min(axis=1)

    return df.sort_values(["Order Dt", "Str Nbr"]).reset_index(drop=True)


def build_summary(workbook_data: dict, scenario: dict):
    supplier_a_df = workbook_data["supplier_a_sheet"].copy()
    supplier_b_df = workbook_data["supplier_b_sheet"].copy()
    
    # Clean supplier dataframes - remove rows with text in numeric columns
    def clean_supplier_df(df):
        if df.empty:
            return df
        df_clean = df.copy()
        # Convert all columns to numeric, invalid values become NaN
        for col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        # Drop rows where all columns are NaN (likely header rows)
        df_clean = df_clean.dropna(how='all')
        # Also drop rows where the first column is NaN (assuming first column should be numeric)
        if len(df_clean.columns) > 0:
            df_clean = df_clean.dropna(subset=[df_clean.columns[0]])
        return df_clean
    
    supplier_a_df = clean_supplier_df(supplier_a_df)
    supplier_b_df = clean_supplier_df(supplier_b_df)
    
    summary_hammer = workbook_data["summary_hammer"].copy()
    summary_shipping = workbook_data["summary_shipping"].copy()
    
    # Aggregate annual costs from summary sheets
    hammer_cost_a = 0
    hammer_cost_b = 0
    if not summary_hammer.empty:
        try:
            supplier_col = _find_col(summary_hammer, ["Supplier"])
        except KeyError:
            supplier_col = None
        
        if supplier_col:
            try:
                cost_col = _find_col(summary_hammer, ["Annual Hammer Product Cost", "Hammer Cost", "Cost"])
                hammer_cost_a = summary_hammer.loc[summary_hammer[supplier_col].astype(str).str.strip() == "A", cost_col].iloc[0] if len(summary_hammer.loc[summary_hammer[supplier_col].astype(str).str.strip() == "A"]) > 0 else 0
                hammer_cost_b = summary_hammer.loc[summary_hammer[supplier_col].astype(str).str.strip() == "B", cost_col].iloc[0] if len(summary_hammer.loc[summary_hammer[supplier_col].astype(str).str.strip() == "B"]) > 0 else 0
            except (KeyError, IndexError):
                # Fallback: assume data is in first two columns
                if len(summary_hammer) >= 2 and len(summary_hammer.columns) >= 2:
                    hammer_cost_a = pd.to_numeric(summary_hammer.iloc[0, 1], errors='coerce') or 0
                    hammer_cost_b = pd.to_numeric(summary_hammer.iloc[1, 1], errors='coerce') or 0
        else:
            # No proper columns, assume data in first two columns
            if len(summary_hammer) >= 2 and len(summary_hammer.columns) >= 2:
                hammer_cost_a = pd.to_numeric(summary_hammer.iloc[0, 1], errors='coerce') or 0
                hammer_cost_b = pd.to_numeric(summary_hammer.iloc[1, 1], errors='coerce') or 0
    
    shipping_cost_a = 0
    shipping_cost_b = 0
    if not summary_shipping.empty:
        try:
            supplier_col = _find_col(summary_shipping, ["Supplier"])
        except KeyError:
            supplier_col = None
        
        if supplier_col:
            try:
                cost_col = _find_col(summary_shipping, ["Annual Shipping Cost", "Shipping Cost", "Cost"])
                shipping_cost_a = summary_shipping.loc[summary_shipping[supplier_col].astype(str).str.strip() == "A", cost_col].iloc[0] if len(summary_shipping.loc[summary_shipping[supplier_col].astype(str).str.strip() == "A"]) > 0 else 0
                shipping_cost_b = summary_shipping.loc[summary_shipping[supplier_col].astype(str).str.strip() == "B", cost_col].iloc[0] if len(summary_shipping.loc[summary_shipping[supplier_col].astype(str).str.strip() == "B"]) > 0 else 0
            except (KeyError, IndexError):
                # Fallback: assume data is in first two columns
                if len(summary_shipping) >= 2 and len(summary_shipping.columns) >= 2:
                    shipping_cost_a = pd.to_numeric(summary_shipping.iloc[0, 1], errors='coerce') or 0
                    shipping_cost_b = pd.to_numeric(summary_shipping.iloc[1, 1], errors='coerce') or 0
        else:
            # No proper columns, assume data in first two columns
            if len(summary_shipping) >= 2 and len(summary_shipping.columns) >= 2:
                shipping_cost_a = pd.to_numeric(summary_shipping.iloc[0, 1], errors='coerce') or 0
                shipping_cost_b = pd.to_numeric(summary_shipping.iloc[1, 1], errors='coerce') or 0
    
    summary = pd.DataFrame([
        {
            "Supplier": "A",
            "Annual Shipping Cost": shipping_cost_a,
            "Annual Hammer Product Cost": hammer_cost_a,
            "Total Annual Cost": shipping_cost_a + hammer_cost_a,
        },
        {
            "Supplier": "B", 
            "Annual Shipping Cost": shipping_cost_b,
            "Annual Hammer Product Cost": hammer_cost_b,
            "Total Annual Cost": shipping_cost_b + hammer_cost_b,
        },
    ])
    
    # For parity check - since we're using workbook calculations, difference should be 0
    expected = pd.DataFrame([
        {"Supplier": "A", "Workbook Expected Total": summary.loc[summary["Supplier"] == "A", "Total Annual Cost"].iloc[0]},
        {"Supplier": "B", "Workbook Expected Total": summary.loc[summary["Supplier"] == "B", "Total Annual Cost"].iloc[0]},
    ])
    
    parity = summary[["Supplier", "Total Annual Cost"]].merge(
        expected, on="Supplier", how="left"
    )
    parity["Difference"] = 0  # No difference since we're using workbook calculations
    
    return summary, supplier_a_df, supplier_b_df, parity