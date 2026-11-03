from datetime import date, datetime
import pandas as pd
import streamlit as st

# 1. 網頁基本設定
st.set_page_config(
    page_title="SmartEXP 智能庫存與效期管理系統", page_icon="📦", layout="wide"
)

DATA_FILE = "Stock_Log.csv"


# 2. 載入或初始化資料庫 (CSV 檔案)
def load_data():
  try:
    df = pd.read_csv(DATA_FILE)
    # 確保日期欄位轉為 Python 日期格式
    for col in ["製造日", "有效日", "開封日"]:
      if col in df.columns:
        df[col] = pd.to_datetime(df[col]).dt.date
    return df
  except FileNotFoundError:
    # 初始建立空的表格 (已移除批號與位置)
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

  # 若有效日為空白/無效，回傳空白
  if pd.isna(exp_date):
    return "", ""

  # 剩餘天數 = 有效日 - 今天
  remaining_days = (exp_date - today).days

  # 燈號判定分支
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


# 載入現有資料
df = load_data()

st.title("📦 SmartEXP 智能庫存與效期管理系統")
st.markdown("基於 **Python (Streamlit + Pandas)** 打造的輕量化行動效期追蹤 App")

# --- 側邊欄：新增/登錄商品表單 ---
st.sidebar.header("➕ 新增庫存商品")
with st.sidebar.form("add_stock_form"):
  barcode = st.text_input("商品條碼 (手機點擊可呼叫相機掃描)")
  name = st.text_input("品名")
  mfg_date = st.date_input("製造日", value=date.today())
  exp_date = st.date_input("有效日", value=date.today())
  item_type = st.selectbox("類型", ["正貨", "試用品"])

  # 試用品開封日勾選與輸入
  has_opened = st.checkbox("是否已開封 (試用品選填)")
  open_date = (
      st.date_input("開封日", value=date.today()) if has_opened else None
  )

  qty = st.number_input("數量", min_value=1, value=1)

  submitted = st.form_submit_button("確認新增存檔")

  if submitted:
    if not name or not barcode:
      st.sidebar.error("⚠️ 請填寫商品條碼與品名！")
    else:
      today = date.today()
      rem_days, status = calculate_status(
          {
              "有效日": exp_date,
              "開封日": open_date if has_opened else pd.NaT,
              "類型": item_type,
          },
          today,
      )

      new_row = {
          "條碼": str(barcode),
          "品名": name,
          "製造日": mfg_date,
          "有效日": exp_date,
          "開封日": open_date if has_opened else pd.NaT,
          "類型": item_type,
          "數量": qty,
          "剩餘天數": rem_days,
          "燈號": status,
      }

      df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
      df.to_csv(DATA_FILE, index=False)
      st.sidebar.success("✅ 成功新增資料！")
      st.rerun()

# --- 主畫面：現有庫存與動態燈號 ---
st.subheader("📋 現有庫存清單與即時效期監控")

if not df.empty:
  # 每次開啟畫面自動以當天日期重新計算所有商品天數與燈號
  today = date.today()
  updated_rows = []
  for _, row in df.iterrows():
    rem_days, status = calculate_status(row, today)
    row["剩餘天數"] = rem_days
    row["燈號"] = status
    updated_rows.append(row)

  df = pd.DataFrame(updated_rows)
  df.to_csv(DATA_FILE, index=False)

  # 顯示庫存表格
  st.dataframe(df, use_container_width=True)

  # 刪除與管理功能
  with st.expander("🗑️ 管理與刪除舊資料"):
    delete_index = st.number_input(
        "選擇要刪除的資料列編號 (Index)",
        min_value=0,
        max_value=max(0, len(df) - 1),
        step=1,
    )
    if st.button("確認刪除該筆資料"):
      df = df.drop(delete_index).reset_index(drop=True)
      df.to_csv(DATA_FILE, index=False)
      st.success(f"已成功刪除第 {delete_index} 筆庫存紀錄！")
      st.rerun()
else:
  st.info("目前尚無庫存資料，請透過左側選單新增商品。")
