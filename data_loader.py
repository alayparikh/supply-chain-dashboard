import pandas as pd

REQUIRED_SHEETS = {
    "Product Info": "product_info",
    "Carrier Rates": "carrier_rates",
    "Historical Orders": "historical_orders",
    "Historical Shipments": "historical_shipments",
    "Weekly Hammer Demand": "weekly_hammer_demand",
    "Supplier A": "supplier_a_sheet",
    "Supplier B": "supplier_b_sheet",
    "Summary  Hammer": "summary_hammer",
    "Summary  Total shipping cost": "summary_shipping",
}

DEFAULT_HAMMER_COSTS = {"A": 0.80, "B": 0.82}


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_workbook_data(path: str) -> dict:
    sheets = pd.read_excel(path, sheet_name=None)
    sheets = {k: _clean_columns(v) for k, v in sheets.items()}

    missing = [name for name in REQUIRED_SHEETS if name not in sheets]
    if missing:
        raise ValueError(f"Missing required sheets: {missing}")

    return {out_key: sheets[sheet_name] for sheet_name, out_key in REQUIRED_SHEETS.items()}


def build_defaults_from_workbook(workbook_data: dict, hammer_costs: dict | None = None) -> dict:
    product_info = workbook_data["product_info"].copy()
    carrier_rates = workbook_data["carrier_rates"].copy()

    hammer_row = product_info.loc[
        product_info["Product Desc"].astype(str).str.strip().str.lower() == "hammer"
    ]
    if hammer_row.empty:
        raise ValueError("Hammer row not found in Product Info sheet.")

    hammer_weight = float(hammer_row["Weight"].iloc[0])

    return {
        "growth_factor": 1.10,
        "hammer_weight": hammer_weight,
        "hammer_costs": hammer_costs or DEFAULT_HAMMER_COSTS,
        "product_info": product_info,
        "carrier_rates": carrier_rates,
    }