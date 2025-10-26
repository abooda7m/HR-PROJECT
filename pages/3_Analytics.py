# -*- coding: utf-8 -*-
#   Analytics from APPROVED only
# - Reads approved records from Approved sheet (via list_approved if available),
#   and gracefully falls back to list_requests(status="approved") if needed.
# - Arabic UI labels, robust parsing, and CSV export of the filtered view.

import streamlit as st
import pandas as pd

# Try to import list_approved; if not present, fall back to list_requests
try:
    from utils.sheets import list_approved  # optional helper (if you added it)
    HAS_LIST_APPROVED = True
except Exception:
    HAS_LIST_APPROVED = False
from utils.sheets import list_requests  # fallback

st.set_page_config(page_title="Analytics", layout="wide")
st.title(" Analytics")

# -------- Data load (Approved only) --------
if HAS_LIST_APPROVED:
    df = list_approved()
else:
    # Fallback: derive from Requests but filter approved only
    df = list_requests(status="approved")

# Guard: empty
if df is None or df.empty:
    st.info("لا توجد بيانات معتمدة بعد.")
    st.stop()

# Coerce types
df = df.copy()
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0.0)

# Filter widgets
c1, c2 = st.columns(2)
with c1:
    min_d = pd.to_datetime(df["date"]).min()
    max_d = pd.to_datetime(df["date"]).max()
    default_start = min_d.date() if pd.notnull(min_d) else None
    default_end   = max_d.date() if pd.notnull(max_d) else None
    date_range = st.date_input("الفترة", value=(default_start, default_end))
with c2:
    # Since we use Approved only, status is fixed. Show a disabled pill for clarity.
    st.text_input("الحالة", value="approved", disabled=True)

# Apply date filter
if isinstance(date_range, (list, tuple)) and len(date_range) == 2 and all(date_range):
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    df = df[(df["date"] >= start) & (df["date"] <= end + pd.Timedelta(days=1))]

# Guard after filter
if df.empty:
    st.info("لا توجد بيانات ضمن الفترة المحددة.")
    st.stop()

# -------- KPIs --------
total_hours = float(df["hours"].sum())
total_requests = int(df.shape[0])
unique_members = int(df[["member_id", "name"]].drop_duplicates().shape[0])

k1, k2, k3 = st.columns(3)
k1.metric("إجمالي الساعات (معتمدة)", f"{total_hours:.2f}")
k2.metric("عدد الطلبات (معتمدة)", f"{total_requests}")
k3.metric("عدد الأعضاء", f"{unique_members}")

st.divider()



# -------- By member (Top 15) --------
st.subheader("ساعات لكل عضو (Top 15)")
by_member = (
    df.groupby(["member_id", "name"], dropna=False)["hours"]
      .sum().reset_index()
      .sort_values("hours", ascending=False)
      .head(15)
)
st.dataframe(by_member.rename(columns={"member_id": "الرقم الجامعي", "name": "الاسم", "hours": "الساعات"}),
             use_container_width=True , hide_index=True)
if not by_member.empty:
    st.bar_chart(by_member.set_index("name")["hours"])

st.divider()

# -------- By department --------
st.subheader("ساعات حسب القسم")
# ملاحظة: نفكّ القسم من notes بصيغة: "{dept} - {task} - {minutes} دقيقة"
dept_col = df["notes"].fillna("").str.split(" - ").str[0]
by_dept = (
    df.assign(القسم=dept_col)
      .groupby("القسم", dropna=False)["hours"].sum()
      .reset_index()
      .sort_values("hours", ascending=False)
)
st.dataframe(by_dept.rename(columns={"hours": "الساعات"}), use_container_width=True , hide_index=True)
if not by_dept.empty:
    st.bar_chart(by_dept.set_index("القسم")["hours"])

st.divider()

# -------- By task (Top 15) --------
st.subheader("أكثر المهام تنفيذًا")
task_col = df["notes"].fillna("").str.split(" - ").str[1]
by_task = (
    df.assign(المهمة=task_col)
      .groupby("المهمة", dropna=False)["hours"].sum()
      .reset_index()
      .sort_values("hours", ascending=False)
      .head(15)
)
st.dataframe(by_task.rename(columns={"hours": "الساعات"}), use_container_width=True , hide_index=True)
if not by_task.empty:
    st.bar_chart(by_task.set_index("المهمة")["hours"])

# -------- Download filtered CSV --------
st.divider()
st.download_button(
    "تنزيل CSV بالنتائج",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="analytics_approved_filtered.csv",
    mime="text/csv",
)
