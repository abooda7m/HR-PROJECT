import streamlit as st
from datetime import date
import pandas as pd

from utils.sheets import (
    list_departments, list_members_by_dept, list_tasks_by_dept,
    append_request_from_selection, list_requests,
    approve_request, reject_request, summary_by_member,
    COL_AR_NAME
)

st.set_page_config(page_title="HR Hours System", page_icon="⏱️", layout="wide")

st.sidebar.title("⏱️ HR Hours System")
page = st.sidebar.radio("اختر الواجهة", ["Member Form", "HR Review", "Analytics"], index=0)

if page == "Member Form":
    st.title("📝 إرسال الساعات (اختيار فقط)")

    depts = list_departments()
    if not depts:
        st.error("لا توجد أقسام في Member_Data.")
        st.stop()
    dept = st.selectbox("القسم", options=depts)

    member_row = None
    task_row = None

    if dept:
        members_df = list_members_by_dept(dept)
        if members_df.empty:
            st.warning("لا توجد أسماء ضمن هذا القسم في Member_Data.")
        member_names = members_df[COL_AR_NAME].astype(str).tolist()
        sel_member = st.selectbox("الاسم", options=member_names if member_names else [])
        if member_names and sel_member:
            member_row = members_df[members_df[COL_AR_NAME] == sel_member].iloc[0]

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

elif page == "HR Review":
    st.title("✅ HR Review & Dashboard")

    st.subheader("Pending Requests")
    pending_df = list_requests(status="pending")
    st.dataframe(pending_df, use_container_width=True)

    st.divider()
    st.subheader("Approve / Reject")

    col1, col2, col3 = st.columns(3)
    with col1:
        target_id = st.number_input("Request ID", step=1, min_value=1)
    with col2:
        hr_name = st.text_input("HR Name *")
    with col3:
        hr_notes = st.text_input("HR Notes (optional)")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Approve"):
            if not hr_name:
                st.error("HR Name is required.")
            else:
                ok = approve_request(int(target_id), hr_name, hr_notes)
                st.success("Approved.") if ok else st.error("ID not found.")
    with c2:
        if st.button("Reject"):
            if not hr_name:
                st.error("HR Name is required.")
            else:
                ok = reject_request(int(target_id), hr_name, hr_notes)
                st.warning("Rejected.") if ok else st.error("ID not found.")

    st.divider()
    st.subheader("Approved Hours Summary (per member)")
    sum_df = summary_by_member("approved")
    st.dataframe(sum_df, use_container_width=True)

else:
    st.title("📊 Analytics")

    df = list_requests()
    if df.empty:
        st.info("لا توجد بيانات بعد.")
        st.stop()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")

    c1, c2 = st.columns(2)
    with c1:
        min_d = pd.to_datetime(df["date"]).min()
        max_d = pd.to_datetime(df["date"]).max()
        date_range = st.date_input("الفترة", value=(min_d.date() if pd.notnull(min_d) else None,
                                                    max_d.date() if pd.notnull(max_d) else None))
    with c2:
        status = st.selectbox("الحالة", options=["all", "pending", "approved", "rejected"], index=0)

    if isinstance(date_range, tuple) and len(date_range) == 2 and all(date_range):
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df = df[(df["date"] >= start) & (df["date"] <= end + pd.Timedelta(days=1))]
    if status != "all":
        df = df[df["status"] == status]

    total_hours = float(df["hours"].fillna(0).sum())
    total_requests = int(df.shape[0])
    approv_rate = (df["status"].eq("approved").mean()*100.0) if total_requests else 0.0

    k1, k2, k3 = st.columns(3)
    k1.metric("إجمالي الساعات", f"{total_hours:.2f}")
    k2.metric("عدد الطلبات", f"{total_requests}")
    k3.metric("نسبة الاعتماد", f"{approv_rate:.1f}%")

    st.divider()

    st.subheader("ساعات لكل عضو (Top 15)")
    by_member = (df.groupby(["member_id","name"], dropna=False)["hours"]
                   .sum().reset_index().sort_values("hours", ascending=False).head(15))
    st.dataframe(by_member, use_container_width=True)
    st.bar_chart(by_member.set_index("name")["hours"])

    st.divider()

    st.subheader("ساعات حسب القسم")
    dept = df["notes"].fillna("").str.split(" - ").str[0]
    by_dept = df.assign(dept=dept).groupby("dept")["hours"].sum().reset_index().sort_values("hours", ascending=False)
    st.dataframe(by_dept, use_container_width=True)
    if not by_dept.empty and "dept" in by_dept.columns:
        st.bar_chart(by_dept.set_index("dept")["hours"])

    st.divider()

    st.subheader("أكثر المهام تنفيذًا")
    task = df["notes"].fillna("").str.split(" - ").str[1]
    by_task = df.assign(task=task).groupby("task")["hours"].sum().reset_index().sort_values("hours", ascending=False).head(15)
    st.dataframe(by_task, use_container_width=True)
    if not by_task.empty and "task" in by_task.columns:
        st.bar_chart(by_task.set_index("task")["hours"])

    st.download_button("تنزيل CSV بالنتائج", data=df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="analytics_filtered.csv", mime="text/csv")
