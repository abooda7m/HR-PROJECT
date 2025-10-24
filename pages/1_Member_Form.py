import streamlit as st
from datetime import date

from utils.sheets import (
    list_departments, list_members_by_dept, list_tasks_by_dept,
    append_request_from_selection, COL_AR_NAME
)

st.set_page_config(page_title="Member Form", page_icon="📝", layout="centered")
st.title("📝 إرسال الساعات (اختيار فقط)")

depts = list_departments()
if not depts:
    st.error("لا توجد أقسام في Member_Data.")
dept = st.selectbox("القسم", options=depts if depts else [])

member_row = None
task_row = None

if dept:
    # Members of selected department
    members_df = list_members_by_dept(dept)
    if members_df.empty:
        st.warning("لا توجد أسماء ضمن هذا القسم في Member_Data.")
    member_names = members_df[COL_AR_NAME].astype(str).tolist()
    sel_member = st.selectbox("الاسم", options=member_names if member_names else [])
    if member_names and sel_member:
        member_row = members_df[members_df[COL_AR_NAME] == sel_member].iloc[0]

    # Tasks of selected department
    tasks_df = list_tasks_by_dept(dept)
    if tasks_df.empty:
        st.warning("لا توجد مهام لهذا القسم في Tasks_Data.")
    else:
        tasks_df = tasks_df.copy()
        tasks_df["label"] = tasks_df.apply(
            lambda r: f"{r['المهمة']} — {int(r['المدة المقترحة ( بالدقائق)'])} دقيقة",
            axis=1
        )
        labels = tasks_df["label"].tolist()
        sel_task = st.selectbox("المهمة", options=labels if labels else [])
        if labels and sel_task:
            task_row = tasks_df[tasks_df["label"] == sel_task].iloc[0]
            minutes = float(task_row["المدة المقترحة ( بالدقائق)"])
            hours = round(minutes / 60.0, 2)
            st.info(f"الساعات المحسوبة: **{hours} ساعة**")

# Date
date_val = st.date_input("التاريخ", value=date.today())

disabled = not (dept and member_row is not None and task_row is not None and date_val)
if st.button("إرسال الطلب", type="primary", disabled=not disabled):
    req_id = append_request_from_selection(
        dept=dept,
        member_row=member_row,
        task_row=task_row,
        date_str=date_val.isoformat(),
    )
    st.success(f"تم الإرسال. رقم الطلب: #{req_id}")
