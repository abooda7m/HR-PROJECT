# utils/sheets.py
# Google Sheets integration (single spreadsheet with sheets: Member_Data, Tasks_Data, Requests, Approved)

import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime
from dateutil import parser
import streamlit as st

# ----- OAuth scopes -----
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ----- Sheet titles -----
SHEET_MEMBERS   = "Member_Data"
SHEET_TASKS     = "Tasks_Data"
SHEET_REQUESTS  = "Requests"
SHEET_APPROVED  = "Approved"

# Member_Data (Arabic headers)
COL_AR_NAME = "الاسم باللغة العربي"
COL_EN_NAME = "الاسم باللغة الإنجليزية"  # optional
COL_NAT_ID  = "رقم الهوية"               # optional
COL_STUD_ID = "الرقم الجامعي"
COL_EMAIL   = "البريد الإلكتروني الشخصي" # optional
COL_PHONE   = "رقم الجوال"               # optional
COL_DEPT    = "Department"

# Tasks_Data (Arabic headers)
COL_TASK_NAME    = "المهمة"
COL_TASK_MINUTES = "المدة المقترحة ( بالدقائق)"
COL_TASK_DEPT    = "القسم"

# ----- Spreadsheet helpers -----
def _client():
    sa = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    return gspread.authorize(creds)

def _open_spreadsheet():
    gc = _client()
    return gc.open(st.secrets["sheets"]["spreadsheet_name"])

def _ws(sh, title):
    return sh.worksheet(title)

def _read_df(ws) -> pd.DataFrame:
    # Drop fully empty rows
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

def _utc_now_str():
    return datetime.utcnow().isoformat(timespec="seconds")

# ----- Ensure sheets (Requests / Approved) -----
def _ensure_requests_sheet(sh):
    """Ensure 'Requests' exists with headers; create if missing."""
    headers = ["id","name","member_id","date","hours","notes","status",
               "hr_name","hr_notes","created_at","approved_at"]
    try:
        ws = _ws(sh, SHEET_REQUESTS)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_REQUESTS, rows=1000, cols=len(headers))
        ws.update('A1:K1', [headers])
        return ws
    # make sure all columns exist
    df = _read_df(ws)
    df = _ensure_cols(df, headers)
    _write_df(ws, df)
    return ws

def _ensure_approved_sheet(sh):
    """Ensure 'Approved' exists with headers; create if missing."""
    headers = ["id","name","member_id","date","hours","notes",
               "hr_name","hr_notes","approved_at"]
    try:
        ws = _ws(sh, SHEET_APPROVED)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_APPROVED, rows=1000, cols=len(headers))
        ws.update('A1:I1', [headers])
        return ws
    # align columns
    df = _read_df(ws)
    df = _ensure_cols(df, headers)
    # keep only the above headers (in order)
    df = df[headers] if not df.empty else pd.DataFrame(columns=headers)
    _write_df(ws, df)
    return ws

# ----- Cached readers -----
@st.cache_data(ttl=60)
def get_members_df() -> pd.DataFrame:
    """Read Member_Data; keep needed columns only."""
    sh = _open_spreadsheet()
    df = _read_df(_ws(sh, SHEET_MEMBERS))
    req = [COL_AR_NAME, COL_STUD_ID, COL_DEPT]
    df = _ensure_cols(df, req)
    df = df.dropna(subset=[COL_AR_NAME, COL_DEPT], how="any")
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
    df[COL_TASK_DEPT] = df[COL_TASK_DEPT].astype(str).str.strip()
    df[COL_TASK_NAME] = df[COL_TASK_NAME].astype(str).str.strip()
    df[COL_TASK_MINUTES] = pd.to_numeric(df[COL_TASK_MINUTES], errors="coerce")
    df = df.dropna(subset=[COL_TASK_DEPT, COL_TASK_NAME, COL_TASK_MINUTES], how="any")
    return df

# ----- Dropdown helpers -----
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

# ----- Requests ops -----
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
    # Sort newest first by created_at then id
    return df.sort_values(by=["created_at","id"], ascending=[False, False]).reset_index(drop=True)

def append_request_from_selection(dept: str, member_row: pd.Series, task_row: pd.Series, date_str: str) -> int:
    """Append to Requests using chosen department, member, and task."""
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
        "created_at": _utc_now_str(),
        "approved_at": None,
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    _write_df(ws, df)

    # Clear caches so UI reflects changes instantly
    st.cache_data.clear()
    return new_row["id"]

def _upsert_approved_row(sh, record: dict):
    """Insert or update a row in 'Approved' sheet by id."""
    ws_appr = _ensure_approved_sheet(sh)
    df_appr = _read_df(ws_appr)
    headers = ["id","name","member_id","date","hours","notes","hr_name","hr_notes","approved_at"]
    df_appr = _ensure_cols(df_appr, headers)

    # Coerce id/hours types
    rec = {
        "id": int(record.get("id")),
        "name": record.get("name"),
        "member_id": record.get("member_id"),
        "date": record.get("date"),
        "hours": pd.to_numeric(record.get("hours"), errors="coerce"),
        "notes": record.get("notes"),
        "hr_name": record.get("hr_name"),
        "hr_notes": record.get("hr_notes"),
        "approved_at": record.get("approved_at") or _utc_now_str(),
    }

    mask = pd.to_numeric(df_appr["id"], errors="coerce").astype("Int64") == rec["id"]
    if mask.any():
        # Update in place
        for k, v in rec.items():
            df_appr.loc[mask, k] = v
    else:
        df_appr = pd.concat([df_appr, pd.DataFrame([rec])], ignore_index=True)

    # Keep columns ordered
    df_appr = df_appr[headers]
    _write_df(ws_appr, df_appr)

def approve_request(target_id: int, hr_name: str, hr_notes: str = "") -> bool:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["id","status","hr_name","hr_notes","approved_at"])

    mask = pd.to_numeric(df["id"], errors="coerce").astype("Int64") == int(target_id)
    if not mask.any():
        return False

    # Guard: already processed?
    current_status = str(df.loc[mask, "status"].iloc[0] or "").lower()
    if current_status == "approved":
        # Still update HR fields if changed; and make sure in Approved sheet
        df.loc[mask, "hr_name"] = (hr_name or "").strip()
        df.loc[mask, "hr_notes"] = (hr_notes or "").strip()
        df.loc[mask, "approved_at"] = _utc_now_str()
    else:
        df.loc[mask, "status"] = "approved"
        df.loc[mask, "hr_name"] = (hr_name or "").strip()
        df.loc[mask, "hr_notes"] = (hr_notes or "").strip()
        df.loc[mask, "approved_at"] = _utc_now_str()

    _write_df(ws, df)

    # Mirror to Approved sheet
    # Build a record dict from the updated row
    row = df.loc[mask].iloc[0].to_dict()
    _upsert_approved_row(sh, row)

    # Clear caches so UI refreshes
    st.cache_data.clear()
    return True

def reject_request(target_id: int, hr_name: str, hr_notes: str = "") -> bool:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["id","status","hr_name","hr_notes","approved_at"])

    mask = pd.to_numeric(df["id"], errors="coerce").astype("Int64") == int(target_id)
    if not mask.any():
        return False

    current_status = str(df.loc[mask, "status"].iloc[0] or "").lower()
    if current_status == "approved":
        # Optional: prevent changing approved to rejected. Uncomment to enforce.
        # return False
        pass

    df.loc[mask, "status"] = "rejected"
    df.loc[mask, "hr_name"] = (hr_name or "").strip()
    df.loc[mask, "hr_notes"] = (hr_notes or "").strip()
    df.loc[mask, "approved_at"] = None
    _write_df(ws, df)

    # No mirroring to Approved for rejected requests

    st.cache_data.clear()
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
