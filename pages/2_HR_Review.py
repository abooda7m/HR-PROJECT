# -*- coding: utf-8 -*-
# 2_HR_Review.py
# HR dashboard: review pending requests, approve/reject, and see summaries.
# - Request selection is a dropdown of current pending requests (no manual ID input).
# - HR Name is a dropdown from list_hr_names().

import streamlit as st
import pandas as pd

from utils.sheets import (
    list_requests,
    approve_request,
    reject_request,
    summary_by_member,
    list_hr_names,
)

st.set_page_config(page_title="HR Review", layout="wide")
st.title(" HR Review & Dashboard")

# --- Pending Requests table ---
st.subheader("Pending Requests")
pending_df = list_requests(status="pending")
st.dataframe(pending_df, use_container_width=True)

st.divider()
st.subheader("Approve / Reject")

# ---------- Request dropdown (only pending) ----------
selected_id = None
if pending_df.empty:
    st.info("لا توجد طلبات قيد الانتظار.")
else:
    # Build a readable label per pending row to avoid manual ID entry
    def _make_label(row: pd.Series) -> str:
        rid = int(row.get("id", 0)) if pd.notna(row.get("id")) else 0
        nm  = str(row.get("name", "") or "").strip()
        dt  = str(row.get("date", "") or "").strip()
        hrs = str(row.get("hours", "") or "").strip()
        nts = str(row.get("notes", "") or "").strip()
        return f"#{rid} — {nm} — {dt} — {hrs}h — {nts}"

    pending_df = pending_df.copy()
    pending_df["__label__"] = pending_df.apply(_make_label, axis=1)

    sel_label = st.selectbox(
        "Request (pending only)",
        options=pending_df["__label__"].tolist(),
        index=None,
        placeholder="Select a pending request",
    )
    if sel_label:
        selected_id = int(pending_df.loc[pending_df["__label__"] == sel_label, "id"].iloc[0])

# ---------- HR Name dropdown ----------
hr_names = list_hr_names()
if hr_names:
    hr_name = st.selectbox("HR Name *", options=hr_names, index=None, placeholder="Select HR name")
else:
    hr_name = None
    st.warning("لا توجد أسماء مهيأة للجنة HR. أضف الأسماء في الأسرار أو تحت قسم HR في Member_Data.")

hr_notes = st.text_input("HR Notes (optional)")

# Buttons are disabled unless both a request and an HR name are selected
approve_disabled = not (selected_id and hr_name)
reject_disabled  = not (selected_id and hr_name)

col_a, col_b = st.columns(2)

with col_a:
    if st.button("Approve", type="primary", disabled=approve_disabled):
        # Optional guard: ensure ID still pending (avoid approving already-processed ID)
        if pending_df.empty or selected_id not in pending_df["id"].astype(int).tolist():
            st.error("الطلب المحدد لم يعد ضمن قائمة الانتظار. حدّث الصفحة واختر مجددًا.")
        else:
            ok = approve_request(int(selected_id), str(hr_name).strip(), hr_notes.strip())
            if ok:
                st.success(f"تمت الموافقة على الطلب #{int(selected_id)}")
                st.rerun()
            else:
                st.error("تعذّر تنفيذ الموافقة. تحقق من الطلب المحدد.")

with col_b:
    if st.button("Reject", disabled=reject_disabled):
        if pending_df.empty or selected_id not in pending_df["id"].astype(int).tolist():
            st.error("الطلب المحدد لم يعد ضمن قائمة الانتظار. حدّث الصفحة واختر مجددًا.")
        else:
            ok = reject_request(int(selected_id), str(hr_name).strip(), hr_notes.strip())
            if ok:
                st.warning(f"تم رفض الطلب #{int(selected_id)}")
                st.rerun()
            else:
                st.error("تعذّر تنفيذ الرفض. تحقق من الطلب المحدد.")

st.divider()
st.subheader("Approved Hours Summary (per member)")
sum_df = summary_by_member("approved")
st.dataframe(sum_df, use_container_width=True , hide_index=True)
