import streamlit as st

st.set_page_config(page_title="Hours Tracker", page_icon="⏱️", layout="wide")

st.title("⏱️ Hours Tracker")
st.markdown(
    """
اختر الواجهة من القائمة الجانبية:
- **Member Form**: إرسال الساعات (اختيار فقط)
- **HR Review**: مراجعة واعتماد + ملخص
    """
)
