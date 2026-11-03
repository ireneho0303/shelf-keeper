from datetime import date, datetime
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_qrcode_scanner import qrcode_scanner

# 1. 網頁基本設定
st.set_page_config(
    page_title="SmartEXP 智能庫存與效期管理系統", page_icon="📦", layout="wide"
)

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)


# 載入資料函式 (加上 ttl=0 確保每次讀取都是最新雲端資料)
def load_data():
  try:
    df = conn.read(ttl=0)
    for col in ["製造日", "有效日", "開封日"]:
      if col in df.columns:
        df[col] = pd.to_datetime(df[col]).dt.date
    return df
  except Exception:
    return pd.DataFrame(columns=[
        "條碼",
        "品名",
        "製造日",
        "有效日",
        "開封日",
        "類型",
        "數量",
        "剩餘天數",
        "燈號",
    ])


# 3. 核心燈號與剩餘天數計算邏輯
def calculate_status(row, today):
  exp_date = row["有效日"]
  open_date = row["開封日"]
  item_type = row["類型"]

  if pd.isna(exp_date):
    return "", ""

  exp_dt = (
      exp_date
      if isinstance(exp_date, date)
      else datetime.strptime(str(exp_date), "%Y-%m-%d").date()
  )
  remaining_days = (exp_dt - today).days

  if item_type == "試用品":
    if pd.isna(open_date):
      status = "⚪ 尚未開封"
    else:
      open_dt = (
          open_date
          if isinstance(open_date, date)
          else datetime.strptime(str(open_date), "%Y-%m-%d").date()
      )
      days_opened = (today - open_dt).days
      if days_opened > 30:
        status = "🔴 試用品逾期"
      else:
        status = "🟢 試用品正常"
  else:
    if remaining_days <= 0:
      status = "🔴 已過期"
    elif remaining_days <= 30:
      status = "🟡 即將到期"
    else:
      status = "🟢 正常"

  return remaining_days, status


# 讀取現有雲端資料
df = load_data()

st.title("📦 SmartEXP 智能庫存與效期管理系統")
st.markdown("基於 **Python + Google Sheets 雲端自動同步** 的行動效期追蹤 App")

# --- 側邊欄：新增/登錄商品表單 ---
st.sidebar.header("➕ 新增庫存商品")

st.sidebar.subheader("📷 條碼相機掃描")
scan_toggle = st.sidebar.toggle("開啟條碼掃描相機")
scanned_barcode = ""

if scan_toggle:
  result = qrcode_scanner(key="barcode_scanner")
  if result:
    scanned_barcode = str(result)
    st.sidebar.success(f"🎯 成功掃描到條碼：{scanned_barcode}")

with st.sidebar.form("add_stock_form"):
  barcode = st.text_input("商品條碼", value=scanned_barcode)
  name = st.text_input("品名")
  mfg_date = st.date_input("製造日", value=date.today())
  exp_date = st.date_input("有效日", value=date.today())
  item_type = st.selectbox("類型", ["正貨", "試用品"])

  has_opened = st.checkbox("是否已開封 (試用品選填)")
  open_date = (
      st.date_input("開封日", value=date.today()) if has_opened else None
  )

  qty = st.number_input("數量", min_value=1, value=1)

  submitted = st.form_submit_button("確認新增存檔至雲端")

  if submitted:
    if not name or not barcode:
      st.sidebar.error("⚠️ 請填寫商品條碼與品名！")
    else:
      today = date.today()
      rem_days, status = calculate_status(
          {
              "有效日": exp_date,
              "開封日": open_date if has_opened else None,
              "類型": item_type,
          },
          today,
      )

      new_row = {
          "條碼": str(barcode),
          "品名": name,
          "製造日": str(mfg_date),
          "有效日": str(exp_date),
          "開封日": str(open_date) if has_opened else "",
          "類型": item_type,
          "數量": qty,
          "剩餘天數": rem_days,
          "燈號": status,
      }

      # 轉為 DataFrame 並同步回 Google Sheets
      new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
      conn.update(data=new_df)
      st.sidebar.success("✅ 成功同步至 Google 雲端試算表！")
      st.rerun()

# --- 主畫面：現有庫存與動態燈號 ---
st.subheader("📋 現有庫存清單與即時效期監控")

if not df.empty:
  today = date.today()
  updated_rows = []
  for _, row in df.iterrows():
    rem_days, status = calculate_status(row, today)
    row["剩餘天數"] = rem_days
    row["燈號"] = status
    updated_rows.append(row)

  df = pd.DataFrame(updated_rows)

  st.dataframe(df, use_container_width=True)

  with st.expander("🗑️ 管理與刪除舊資料"):
    delete_index = st.number_input(
        "選擇要刪除的資料列編號 (Index)",
        min_value=0,
        max_value=max(0, len(df) - 1),
        step=1,
    )
    if st.button("確認刪除該筆資料"):
      df = df.drop(delete_index).reset_index(drop=True)
      conn.update(data=df)
      st.success(f"已成功自雲端刪除第 {delete_index} 筆庫存紀錄！")
      st.rerun()
else:
  st.info("目前尚無庫存資料，請透過左側選單新增商品。")
