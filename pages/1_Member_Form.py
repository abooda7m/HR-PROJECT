# -*- coding: utf-8 -*-
import streamlit as st
from datetime import date, datetime
import pandas as pd

from utils.sheets import (
    list_departments,
    list_members_by_dept,
    list_tasks_by_dept,
    append_request_from_selection,
)

# Arabic column constants
COL_AR_NAME = "الاسم باللغة العربي"
COL_TASK = "المهمة"
COL_MINUTES = "المدة المقترحة ( بالدقائق)"

st.set_page_config(page_title="Member Form", layout="centered")
st.title("إرسال الساعات")

# --- Departments ---
depts = list_departments()
if not depts:
    st.error("لا توجد أقسام في Member_Data.")
    st.stop()

dept = st.selectbox("القسم", options=depts, index=0)

member_row_df = pd.DataFrame()
task_row_df = pd.DataFrame()

# --- Members & Tasks for selected dept ---
if dept:
    # Members
    members_df = list_members_by_dept(dept)
    if members_df.empty:
        st.warning("لا توجد أسماء ضمن هذا القسم في Member_Data.")
        member_names = []
    else:
        member_names = members_df[COL_AR_NAME].astype(str).tolist()

    sel_member = st.selectbox("الاسم", options=member_names, index=0 if member_names else None, placeholder="اختر الاسم")
    if member_names and sel_member:
        member_row_df = members_df[members_df[COL_AR_NAME] == sel_member].head(1)

    # Tasks
    tasks_df = list_tasks_by_dept(dept)
    if tasks_df.empty:
        st.warning("لا توجد مهام لهذا القسم في Tasks_Data.")
        labels = []
    else:
        tasks_df = tasks_df.copy()
        # Ensure minutes are numeric
        tasks_df[COL_MINUTES] = pd.to_numeric(tasks_df[COL_MINUTES], errors="coerce")
        tasks_df = tasks_df.dropna(subset=[COL_TASK, COL_MINUTES], how="any")
        # Build label
        tasks_df["__label__"] = tasks_df.apply(
            lambda r: f"{r[COL_TASK]} — {int(r[COL_MINUTES])} دقيقة", axis=1
        )
        labels = tasks_df["__label__"].tolist()

    sel_task = st.selectbox("المهمة", options=labels, index=0 if labels else None, placeholder="اختر المهمة")
    if labels and sel_task:
        task_row_df = tasks_df[tasks_df["__label__"] == sel_task].head(1)
        if not task_row_df.empty:
            minutes = float(task_row_df[COL_MINUTES].iloc[0])
            hours = round(minutes / 60.0, 2)
            st.info(f"الساعات المحسوبة: **{hours} ساعة**")

# --- Date picker ---
date_val = st.date_input("التاريخ", value=date.today(), format="YYYY-MM-DD")

# --- Ready flag & submit button ---
ready_to_submit = (
    bool(dept)
    and not member_row_df.empty
    and not task_row_df.empty
    and isinstance(date_val, (date, datetime))
)

if st.button("إرسال الطلب", type="primary", disabled=not ready_to_submit):
    # Final guards
    if member_row_df.empty:
        st.error("العضو غير موجود.")
        st.stop()
    if task_row_df.empty:
        st.error("المهمة غير موجودة.")
        st.stop()
    if not isinstance(date_val, (date, datetime)):
        st.error("صيغة التاريخ غير صحيحة.")
        st.stop()

    # Prepare dicts
    member_row = member_row_df.iloc[0].to_dict()
    task_row = task_row_df.iloc[0].to_dict()

    # Date ISO
    date_str = date_val.date().isoformat() if isinstance(date_val, datetime) else date_val.isoformat()

    # Append to Requests
    req_id = append_request_from_selection(
        dept=dept,
        member_row=member_row,
        task_row=task_row,
        date_str=date_str,
    )

    if req_id is not None:
        st.success(f"تم الإرسال. رقم الطلب: #{req_id}")
    else:
        st.error("حدث خطأ أثناء إرسال الطلب. حاول مرة أخرى.")
