# 2_HR_Review.py
import streamlit as st
from utils.sheets import list_requests, approve_request, reject_request, summary_by_member

st.set_page_config(page_title="HR Review", page_icon="✅", layout="wide")
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

# simple guard: only allow IDs that are pending (optional but clearer UX)
valid_ids = set(map(int, pending_df["id"].dropna().astype(int).tolist())) if not pending_df.empty else set()

c1, c2 = st.columns(2)

with c1:
    if st.button("Approve", type="primary"):
        if not hr_name.strip():
            st.error("HR Name is required.")
        elif int(target_id) not in valid_ids and len(valid_ids) > 0:
            st.error("This Request ID is not in pending list.")
        else:
            ok = approve_request(int(target_id), hr_name.strip(), (hr_notes or "").strip())
            if ok:
                st.success("Approved.")
                st.rerun()
            else:
                st.error("ID not found.")

with c2:
    if st.button("Reject"):
        if not hr_name.strip():
            st.error("HR Name is required.")
        elif int(target_id) not in valid_ids and len(valid_ids) > 0:
            st.error("This Request ID is not in pending list.")
        else:
            ok = reject_request(int(target_id), hr_name.strip(), (hr_notes or "").strip())
            if ok:
                st.warning("Rejected.")
                st.rerun()
            else:
                st.error("ID not found.")

st.divider()
st.subheader("Approved Hours Summary (per member)")
sum_df = summary_by_member("approved")
st.dataframe(sum_df, use_container_width=True)
