# -*- coding: utf-8 -*-
# 5_Period_Admin.py
# - يعرض الـ Anchor الحالي
# - يكوّن Snapshot للفترة الحالية (من Approved منذ الـ Anchor)
# - زر واحد: تنزيل CSV للفترة الحالية + تصفير منطقي (ضبط Anchor الآن وإعادة بناء الورقة)

import streamlit as st
import pandas as pd
from datetime import datetime

from utils.sheets import (
    get_period_anchor,
    set_period_anchor_now,
    list_approved,
    get_members_df,   # لاستخدام نفس الدمج (member_id/name -> Department/national_id) في الـ CSV
)

st.set_page_config(page_title="إدارة الفترة", layout="centered")
st.title(" إدارة فترة الرفع")

# ---------- البيانات الخام (Approved فقط) ----------
app = list_approved().copy()
anchor = get_period_anchor()

st.markdown("**المرجع الزمني الحالي:** " + (str(anchor) if anchor is not None else "غير محدد"))
st.info(
    "سيقوم الزر أدناه بإنشاء ملف بيانات للفترة الحالية (منذ المرجع الزمني)، "
    "ثم ضبط المرجع الزمني على الوقت الحالي وإعادة بناء لوحة فترة الأعضاء. "
    "لن تُحذف أي بيانات سابقة."
)

# ---------- تكوين Snapshot للفترة الحالية ----------
if anchor is not None:
    app = app[app["approved_at_dt"] >= anchor]

# تطبيع مفاتيح الدمج
app["member_id"] = app["member_id"].astype(str).str.replace("\u00a0", " ").str.strip()
app["name"] = app["name"].astype(str).str.strip()

# تجميع ساعات الفترة الحالية لكل عضو
g = (
    app.groupby(["member_id", "name"], dropna=False)
       .agg(total_hours=("hours", "sum"), count=("id", "count"),
            last_approved_at=("approved_at_dt", "max"))
       .reset_index()
)
g["total_hours"] = pd.to_numeric(g["total_hours"], errors="coerce").fillna(0.0).round(2)

# إلحاق بيانات العضو من Member_Data (القسم/الهوية)
members = get_members_df().copy()
if "رقم الهوية" not in members.columns:
    members["رقم الهوية"] = ""  # احتياطي إن ما كان العمود موجود
members = members.rename(columns={
    "الاسم باللغة العربي": "name",
    "الرقم الجامعي": "member_id",
    "Department": "Department",
    "رقم الهوية": "national_id",
})
members["member_id"] = members["member_id"].astype(str).str.replace("\u00a0", " ").str.strip()
members["name"] = members["name"].astype(str).str.strip()

period_df = g.merge(
    members[["member_id", "name", "Department", "national_id"]],
    on=["member_id", "name"], how="left"
)

# تنسيق آخر اعتماد
period_df["last_approved_at"] = (
    pd.to_datetime(period_df["last_approved_at"], utc=True, errors="coerce")
      .dt.tz_convert("UTC")
      .dt.strftime("%Y-%m-%d %H:%M:%S")
      .fillna("")
)

# ترتيب الأعمدة وعرض معاينة
period_df = period_df[
    ["member_id", "national_id", "name", "Department", "total_hours", "count", "last_approved_at"]
].sort_values(["total_hours", "count"], ascending=[False, False]).reset_index(drop=True)

st.subheader("معاينة الفترة الحالية")
st.dataframe(period_df, use_container_width=True, hide_index=True)

# ---------- زر: تنزيل CSV + تصفير الفترة ----------
def _reset_period():
    # يضبط الـ Anchor الآن ويعيد بناء Members_Period
    ts = set_period_anchor_now()
    st.session_state["period_reset_done"] = ts

csv_bytes = period_df.to_csv(index=False).encode("utf-8-sig")
file_name = f"members_period_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

st.download_button(
    label=" تنزيل CSV للفترة الحالية + بدء فترة جديدة",
    data=csv_bytes,
    file_name=file_name,
    mime="text/csv",
    type="primary",
    on_click=_reset_period,   # بعد بدء التنزيل يُضبط الـ Anchor ويُعاد البناء
)

if "period_reset_done" in st.session_state:
    st.success(f"تم ضبط Anchor على: {st.session_state['period_reset_done']}")
    st.caption("تم أيضًا إعادة بناء ورقة Members_Period للفترة الجديدة.")


st.divider()
