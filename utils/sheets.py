# utils/sheets.py
# Google Sheets integration (ملف واحد فيه أوراق: Member_Data, Tasks_Data, Requests)

import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime
from dateutil import parser
import streamlit as st  # for secrets + cache

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet titles
SHEET_MEMBERS   = "Member_Data"
SHEET_TASKS     = "Tasks_Data"
SHEET_REQUESTS  = "Requests"

# Member_Data (Arabic headers)
COL_AR_NAME = "الاسم باللغة العربي"
COL_EN_NAME = "الاسم باللغة الإنجليزية"  # optional
COL_NAT_ID  = "رقم الهوية"
COL_STUD_ID = "الرقم الجامعي"
COL_EMAIL   = "البريد الإلكتروني الشخصي"
COL_PHONE   = "رقم الجوال"
COL_DEPT    = "Department"

# Tasks_Data (Arabic headers)
COL_TASK_NAME    = "المهمة"
COL_TASK_MINUTES = "المدة المقترحة ( بالدقائق)"
COL_TASK_DEPT    = "القسم"

def _client():
    sa = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    return gspread.authorize(creds)

def _open_spreadsheet():
    gc = _client()
    # اسم الملف داخل secrets.toml -> [sheets].spreadsheet_name
    return gc.open(st.secrets["sheets"]["spreadsheet_name"])

def _ws(sh, title):
    return sh.worksheet(title)

def _read_df(ws) -> pd.DataFrame:
    # قراءة مع إسقاط الصفوف الفارغة تمامًا
    return get_as_dataframe(ws, evaluate_formulas=True, header=0).dropna(how="all")

def _write_df(ws, df: pd.DataFrame):
    ws.clear()
    set_with_dataframe(ws, df, include_index=False, include_column_header=True)

def _ensure_cols(df: pd.DataFrame, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df

def _new_id(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce")
    return int(pd.Series(ids).fillna(0).max()) + 1

# --------- يضمن وجود ورقة Requests ويُنشِئها لو مفقودة ---------
def _ensure_requests_sheet(sh):
    """Create 'Requests' sheet with headers if missing."""
    try:
        return _ws(sh, SHEET_REQUESTS)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_REQUESTS, rows=1000, cols=11)
        headers = ["id","name","member_id","date","hours","notes","status",
                   "hr_name","hr_notes","created_at","approved_at"]
        ws.update('A1:K1', [headers])
        return ws

# ---------- Cached readers ----------

@st.cache_data(ttl=60)
def get_members_df() -> pd.DataFrame:
    """Read Member_Data; keep needed columns only."""
    sh = _open_spreadsheet()
    df = _read_df(_ws(sh, SHEET_MEMBERS))
    req = [COL_AR_NAME, COL_STUD_ID, COL_DEPT]
    df = _ensure_cols(df, req)
    # Drop rows with no department or name
    df = df.dropna(subset=[COL_AR_NAME, COL_DEPT], how="any")
    # Normalize to string
    df[COL_DEPT] = df[COL_DEPT].astype(str).str.strip()
    df[COL_AR_NAME] = df[COL_AR_NAME].astype(str).str.strip()
    df[COL_STUD_ID] = df[COL_STUD_ID].astype(str).str.strip()
    return df

@st.cache_data(ttl=60)
def get_tasks_df() -> pd.DataFrame:
    """Read Tasks_Data; coerce minutes to numeric."""
    sh = _open_spreadsheet()
    df = _read_df(_ws(sh, SHEET_TASKS))
    req = [COL_TASK_NAME, COL_TASK_MINUTES, COL_TASK_DEPT]
    df = _ensure_cols(df, req)
    # Clean + types
    df[COL_TASK_DEPT] = df[COL_TASK_DEPT].astype(str).str.strip()
    df[COL_TASK_NAME] = df[COL_TASK_NAME].astype(str).str.strip()
    df[COL_TASK_MINUTES] = pd.to_numeric(df[COL_TASK_MINUTES], errors="coerce")
    # Keep only valid rows
    df = df.dropna(subset=[COL_TASK_DEPT, COL_TASK_NAME, COL_TASK_MINUTES], how="any")
    return df

# ---------- Dropdown helpers ----------

def list_departments():
    """Unique departments from Member_Data."""
    members = get_members_df()
    return sorted(members[COL_DEPT].dropna().unique().tolist())

def list_members_by_dept(dept: str) -> pd.DataFrame:
    members = get_members_df()
    return members[members[COL_DEPT] == str(dept).strip()].copy()

def list_tasks_by_dept(dept: str) -> pd.DataFrame:
    tasks = get_tasks_df()
    return tasks[tasks[COL_TASK_DEPT] == str(dept).strip()].copy()

# ---------- Requests ops ----------

def list_requests(status: str = None) -> pd.DataFrame:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    cols = ["id","name","member_id","date","hours","notes","status",
            "hr_name","hr_notes","created_at","approved_at"]
    df = _ensure_cols(df, cols)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")
    if status:
        df = df[df["status"] == status]
    return df.sort_values(by=["created_at","id"], ascending=[False, False]).reset_index(drop=True)

def append_request_from_selection(dept: str, member_row: pd.Series, task_row: pd.Series, date_str: str) -> int:
    """
    Append to Requests using chosen department, member, and task.
    - hours = minutes / 60 (float, 2 decimals)
    - notes = "<القسم> - <المهمة> - <X> دقيقة"
    """
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    cols = ["id","name","member_id","date","hours","notes","status",
            "hr_name","hr_notes","created_at","approved_at"]
    df = _ensure_cols(df, cols)

    name_ar   = str(member_row.get(COL_AR_NAME) or "").strip()
    studentId = str(member_row.get(COL_STUD_ID) or "").strip()
    task_name = str(task_row.get(COL_TASK_NAME) or "").strip()
    minutes   = float(task_row.get(COL_TASK_MINUTES) or 0.0)
    hours     = round(minutes / 60.0, 2)

    new_row = {
        "id": _new_id(df),
        "name": name_ar,
        "member_id": studentId,
        "date": parser.parse(date_str).date().isoformat() if date_str else None,
        "hours": hours,
        "notes": f"{dept} - {task_name} - {int(minutes)} دقيقة",
        "status": "pending",
        "hr_name": None,
        "hr_notes": None,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "approved_at": None,
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    _write_df(ws, df)
    return new_row["id"]

def approve_request(target_id: int, hr_name: str, hr_notes: str = "") -> bool:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["id"])
    mask = pd.to_numeric(df["id"], errors="coerce").astype("Int64") == int(target_id)
    if not mask.any():
        return False
    df.loc[mask, "status"] = "approved"
    df.loc[mask, "hr_name"] = (hr_name or "").strip()
    df.loc[mask, "hr_notes"] = (hr_notes or "").strip()
    df.loc[mask, "approved_at"] = datetime.utcnow().isoformat(timespec="seconds")
    _write_df(ws, df)
    return True

def reject_request(target_id: int, hr_name: str, hr_notes: str = "") -> bool:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["id"])
    mask = pd.to_numeric(df["id"], errors="coerce").astype("Int64") == int(target_id)
    if not mask.any():
        return False
    df.loc[mask, "status"] = "rejected"
    df.loc[mask, "hr_name"] = (hr_name or "").strip()
    df.loc[mask, "hr_notes"] = (hr_notes or "").strip()
    df.loc[mask, "approved_at"] = None
    _write_df(ws, df)
    return True

def summary_by_member(status_filter: str = "approved") -> pd.DataFrame:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["member_id", "name", "hours", "status", "id"])
    if status_filter:
        df = df[df["status"] == status_filter]
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")
    df = df[df["hours"].notnull()]
    if df.empty:
        return pd.DataFrame(columns=["member_id","name","total_hours","count"])
    agg = (
        df.groupby(["member_id","name"], dropna=False)
          .agg(total_hours=("hours","sum"), count=("id","count"))
          .reset_index()
          .sort_values("total_hours", ascending=False)
    )
    return agg
