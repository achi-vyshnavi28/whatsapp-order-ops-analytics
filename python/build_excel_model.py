"""
Builds excel/financial_ops_model.xlsx from live PostgreSQL data.

Produces a workbook with real Excel formulas (not pasted static values):
  - Monthly Revenue & Orders (raw data pulled from Postgres)
  - Financial Model: MoM growth %, 3-month linear forecast via TREND(),
    freight cost as % of revenue
  - Delivery SLA What-If: models the revenue/review-score impact of
    reducing the late-delivery rate, with adjustable input cells
  - A chart on the Financial Model sheet
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "excel" / "financial_ops_model.xlsx"

ENGINE = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/order_ops_analytics")

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
INPUT_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")


def style_header(ws, row: int, n_cols: int) -> None:
    for c in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")


def autosize(ws, widths: dict[str, int]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def fetch_monthly() -> pd.DataFrame:
    q = """
        SELECT
            DATE_TRUNC('month', o.order_purchase_timestamp)::date AS month,
            COUNT(DISTINCT o.order_id)                             AS orders,
            SUM(oi.price)                                          AS product_revenue,
            SUM(oi.freight_value)                                  AS freight_cost
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.order_status NOT IN ('canceled', 'unavailable')
          AND o.order_purchase_timestamp >= '2017-01-01'
          AND o.order_purchase_timestamp < '2018-09-01'
        GROUP BY 1
        ORDER BY 1;
    """
    return pd.read_sql(q, ENGINE)


def fetch_delivery_summary() -> dict:
    q = """
        SELECT
            COUNT(*) AS delivered_orders,
            SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END) AS late_orders,
            AVG(price_total) AS avg_order_value
        FROM (
            SELECT o.order_id, o.order_delivered_customer_date, o.order_estimated_delivery_date,
                   SUM(oi.price + oi.freight_value) AS price_total
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
            GROUP BY o.order_id, o.order_delivered_customer_date, o.order_estimated_delivery_date
        ) t;
    """
    row = pd.read_sql(q, ENGINE).iloc[0]
    return {
        "delivered_orders": int(row.delivered_orders),
        "late_orders": int(row.late_orders),
        "avg_order_value": float(row.avg_order_value),
    }


def build_monthly_sheet(wb: Workbook, monthly: pd.DataFrame) -> None:
    ws = wb.active
    ws.title = "Monthly Data"
    headers = ["Month", "Orders", "Product Revenue (R$)", "Freight Cost (R$)"]
    ws.append(headers)
    style_header(ws, 1, len(headers))
    for _, r in monthly.iterrows():
        ws.append([r["month"], int(r["orders"]), round(r["product_revenue"], 2), round(r["freight_cost"], 2)])
    autosize(ws, {"A": 14, "B": 10, "C": 20, "D": 18})
    for row in range(2, ws.max_row + 1):
        ws.cell(row=row, column=1).number_format = "yyyy-mm"


def build_financial_model_sheet(wb: Workbook, n_months: int) -> None:
    ws = wb.create_sheet("Financial Model")
    headers = ["Month", "Orders", "Total Revenue (R$)", "MoM Growth %",
               "Freight % of Revenue", "3-Mo Forecast Revenue (R$)"]
    ws.append(headers)
    style_header(ws, 1, len(headers))

    data_last_row = n_months + 1  # in "Monthly Data" sheet
    for i in range(n_months):
        r = i + 2
        src = f"'Monthly Data'!"
        ws.cell(row=r, column=1, value=f"={src}A{r}")
        ws.cell(row=r, column=2, value=f"={src}B{r}")
        ws.cell(row=r, column=3, value=f"=({src}C{r}+{src}D{r})")
        if i == 0:
            ws.cell(row=r, column=4, value=None)
        else:
            ws.cell(row=r, column=4, value=f"=IFERROR((C{r}-C{r-1})/C{r-1},\"\")")
            ws.cell(row=r, column=4).number_format = "0.0%"
        ws.cell(row=r, column=5, value=f"=IFERROR({src}D{r}/({src}C{r}+{src}D{r}),\"\")")
        ws.cell(row=r, column=5).number_format = "0.0%"
        ws.cell(row=r, column=3).number_format = "#,##0.00"
        ws.cell(row=r, column=1).number_format = "yyyy-mm"

    # Month-index helper column (needed as the X range for TREND()).
    ws.cell(row=1, column=7, value="Month Index")
    for i in range(n_months):
        r = i + 2
        ws.cell(row=r, column=7, value=i + 1)

    # 3-month forward linear forecast using TREND() over the full revenue history.
    # Forecast rows start the row AFTER the last actual data row.
    last_data_row = n_months + 1
    for j, months_ahead in enumerate([1, 2, 3]):
        r = last_data_row + 1 + j
        ws.cell(row=r, column=1, value=f"=EDATE($A${last_data_row},{months_ahead})")
        ws.cell(row=r, column=1).number_format = "yyyy-mm"
        ws.cell(row=r, column=7, value=f"={n_months}+{months_ahead}")
        ws.cell(row=r, column=6,
                value=f"=TREND($C$2:$C${last_data_row},$G$2:$G${last_data_row},G{r})")
        ws.cell(row=r, column=6).number_format = "#,##0.00"

    autosize(ws, {"A": 14, "B": 10, "C": 20, "D": 14, "E": 20, "F": 24, "G": 12})

    chart = LineChart()
    chart.title = "Revenue Trend & 3-Month Forecast"
    chart.y_axis.title = "Revenue (R$)"
    chart.x_axis.title = "Month"
    data = Reference(ws, min_col=3, min_row=1, max_row=last_data_row + 3)
    chart.add_data(data, titles_from_data=True)
    fcst = Reference(ws, min_col=6, min_row=1, max_row=last_data_row + 3)
    chart.add_data(fcst, titles_from_data=True)
    cats = Reference(ws, min_col=1, min_row=2, max_row=last_data_row + 3)
    chart.set_categories(cats)
    chart.width = 22
    chart.height = 10
    ws.add_chart(chart, f"I2")


def build_sla_whatif_sheet(wb: Workbook, delivery: dict) -> None:
    ws = wb.create_sheet("Delivery SLA What-If")
    ws["A1"] = "Delivery SLA - Revenue-at-Risk Model"
    ws["A1"].font = Font(bold=True, size=13)

    rows = [
        ("Delivered orders (actual)", delivery["delivered_orders"]),
        ("Late-delivered orders (actual)", delivery["late_orders"]),
        ("Current late-delivery rate", None),
        ("Average order value (R$)", round(delivery["avg_order_value"], 2)),
        ("", None),
        ("--- Adjustable Inputs ---", None),
        ("Target late-delivery rate", 0.05),
        ("Est. repeat-purchase loss per late delivery (%)", 0.15),
        ("Est. avg customer lifetime orders", 2.5),
    ]
    r = 3
    for label, val in rows:
        ws.cell(row=r, column=1, value=label)
        if val is not None:
            cell = ws.cell(row=r, column=2, value=val)
            if "rate" in label.lower() or "%" in label:
                cell.number_format = "0.0%"
                cell.fill = INPUT_FILL
        r += 1

    # Named cell references (by row, computed above): rows 3..11
    ws["B5"] = "=B4/B3"
    ws["B5"].number_format = "0.0%"

    r += 1
    ws.cell(row=r, column=1, value="--- Model Output ---").font = Font(bold=True)
    out_start = r + 1
    outputs = [
        ("Orders that need to shift from 'late' to 'on-time'",
         "=MAX(B4-(B9*B3),0)"),
        ("Revenue currently at risk from late deliveries (R$)",
         "=B4*B6*B10*B11"),
        ("Revenue recovered if target SLA is hit (R$)",
         f"=B{out_start}*B6*B10*B11"),
    ]
    r = out_start
    for label, formula in outputs:
        ws.cell(row=r, column=1, value=label)
        cell = ws.cell(row=r, column=2, value=formula)
        if "Orders" in label:
            cell.number_format = "#,##0"
        else:
            cell.number_format = "#,##0.00"
        r += 1

    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 18

    note_row = r + 2
    ws.cell(row=note_row, column=1,
            value=("Model logic: revenue-at-risk = (late orders) x (repeat-purchase-loss %) x "
                   "(avg customer lifetime orders) x (avg order value). Change the yellow input "
                   "cells (target SLA %, assumed loss rate) to re-run the scenario live."))
    ws.cell(row=note_row, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row + 2, end_column=6)


def main() -> None:
    monthly = fetch_monthly()
    delivery = fetch_delivery_summary()

    wb = Workbook()
    build_monthly_sheet(wb, monthly)
    build_financial_model_sheet(wb, len(monthly))
    build_sla_whatif_sheet(wb, delivery)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_PATH)
    print(f"Workbook written to {OUT_PATH}")


if __name__ == "__main__":
    main()
