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
