# -*- coding: utf-8 -*-
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import pandas as pd
from datetime import datetime
from dateutil import parser
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_MEMBERS   = "Member_Data"
SHEET_TASKS     = "Tasks_Data"
SHEET_REQUESTS  = "Requests"
SHEET_APPROVED  = "Approved"   # existing
SHEET_REJECTED  = "Rejected"   # NEW

# --- NEW rollup sheets ---
SHEET_LEADERBOARD = "Members_Leaderboard"   # مدى الحياة
SHEET_PERIOD      = "Members_Period"        # من نقطة مرجعية
SHEET_META        = "Meta"                  # لتخزين period_anchor

# Columns (do NOT change Arabic labels)
COL_AR_NAME = "الاسم باللغة العربي"
COL_EN_NAME = "الاسم باللغة الإنجليزية"
COL_NAT_ID  = "رقم الهوية"
COL_STUD_ID = "الرقم الجامعي"
COL_EMAIL   = "البريد الإلكتروني الشخصي"
COL_PHONE   = "رقم الجوال"
COL_DEPT    = "Department"

COL_TASK_NAME    = "المهمة"
COL_TASK_MINUTES = "المدة المقترحة ( بالدقائق)"
COL_TASK_DEPT    = "القسم"

# Approved / Rejected headers (exact)
APPROVED_HEADERS = [
    "id", "name", "member_id", "date", "hours", "notes",
    "hr_name", "hr_notes", "approved_at",
]

REJECTED_HEADERS = [
    "id", "name", "member_id", "date", "hours", "notes",
    "hr_name", "hr_notes", "rejected_at",
]

# Rollup headers
LEADER_HEADERS = [
    "member_id", "national_id", "name", "Department",
    "total_hours", "count", "last_approved_at",
]
PERIOD_HEADERS = LEADER_HEADERS[:]  # نفس الهيكل

# ---------------- Core gspread helpers ----------------
def _client():
    sa = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    return gspread.authorize(creds)

def _open_spreadsheet():
    gc = _client()
    name = st.secrets["sheets"]["spreadsheet_name"]
    return gc.open(name)

def _ws(sh, title):
    return sh.worksheet(title)

def _read_df(ws) -> pd.DataFrame:
    """Read worksheet to DataFrame, drop fully empty rows, and clean column names."""
    df = get_as_dataframe(ws, evaluate_formulas=True, header=0).dropna(how="all")
    def _clean_col(c):
        # remove NBSP and extra spaces
        return str(c).replace("\u00a0", " ").strip()
    df.columns = [_clean_col(c) for c in df.columns]
    return df

def _write_df(ws, df: pd.DataFrame):
    ws.clear()
    set_with_dataframe(ws, df, include_index=False, include_column_header=True)

def _ensure_cols(df: pd.DataFrame, cols):
    """Ensure required columns exist; add if missing."""
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df

def _new_id(df: pd.DataFrame) -> int:
    if df.empty or "id" not in df.columns:
        return 1
    ids = pd.to_numeric(df["id"], errors="coerce")
    return int(pd.Series(ids).fillna(0).max()) + 1

def _ensure_requests_sheet(sh):
    try:
        return _ws(sh, SHEET_REQUESTS)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_REQUESTS, rows=1000, cols=11)
        headers = ["id","name","member_id","date","hours","notes","status",
                   "hr_name","hr_notes","created_at","approved_at"]
        ws.update('A1:K1', [headers])
        return ws

def _ensure_approved_sheet(sh):
    """Ensure Approved sheet exists with exact headers."""
    try:
        return _ws(sh, SHEET_APPROVED)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_APPROVED, rows=1000, cols=len(APPROVED_HEADERS))
        ws.update('A1:I1', [APPROVED_HEADERS])
        return ws

def _ensure_rejected_sheet(sh):
    """Ensure Rejected sheet exists with exact headers."""
    try:
        return _ws(sh, SHEET_REJECTED)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_REJECTED, rows=1000, cols=len(REJECTED_HEADERS))
        ws.update('A1:I1', [REJECTED_HEADERS])
        return ws

# --- generic create sheet with headers ---
def _ensure_sheet_with_headers(sh, title, headers):
    try:
        ws = _ws(sh, title)
    except Exception:
        ws = sh.add_worksheet(title=title, rows=2000, cols=len(headers))
        ws.update(f"A1:{chr(64+len(headers))}1", [headers])
        return ws
    first = ws.row_values(1)
    if first != headers:
        ws.update(f"A1:{chr(64+len(headers))}1", [headers])
    return ws

def _ensure_leaderboard_sheet(sh):
    return _ensure_sheet_with_headers(sh, SHEET_LEADERBOARD, LEADER_HEADERS)

def _ensure_period_sheet(sh):
    return _ensure_sheet_with_headers(sh, SHEET_PERIOD, PERIOD_HEADERS)

def _ensure_meta_sheet(sh):
    try:
        return _ws(sh, SHEET_META)
    except Exception:
        ws = sh.add_worksheet(title=SHEET_META, rows=10, cols=2)
        ws.update("A1:B1", [["key","value"]])
        return ws

# ---------------- Normalizers ----------------
def _normalize_member_id(v):
    """Return member_id as clean string (no .0, no spaces)."""
    s = str(v).replace("\u00a0", " ").strip()
    if not s or s.lower() in {"nan", "none"}:
        return ""
    try:
        num = pd.to_numeric(s, errors="coerce")
        if pd.isna(num):
            return s
        return str(int(num)) if float(num).is_integer() else str(num)
    except Exception:
        return s

# ---------------- Cached readers ----------------
@st.cache_data(ttl=60)
def get_members_df() -> pd.DataFrame:
    """Read Member_Data & return cleaned dataframe with normalized member_id."""
    sh = _open_spreadsheet()
    df = _read_df(_ws(sh, SHEET_MEMBERS))
    req = [COL_AR_NAME, COL_STUD_ID, COL_DEPT]
    df = _ensure_cols(df, req)

    df[COL_DEPT]    = df[COL_DEPT].astype(str).str.replace("\u00a0"," ").str.strip()
    df[COL_AR_NAME] = df[COL_AR_NAME].astype(str).str.replace("\u00a0"," ").str.strip()
    df[COL_STUD_ID] = df[COL_STUD_ID].apply(_normalize_member_id)

    df = df.dropna(subset=[COL_AR_NAME, COL_DEPT], how="any")
    return df

@st.cache_data(ttl=60)
def get_tasks_df() -> pd.DataFrame:
    sh = _open_spreadsheet()
    df = _read_df(_ws(sh, SHEET_TASKS))
    req = [COL_TASK_NAME, COL_TASK_MINUTES, COL_TASK_DEPT]
    df = _ensure_cols(df, req)
    df[COL_TASK_DEPT] = df[COL_TASK_DEPT].astype(str).str.strip()
    df[COL_TASK_NAME] = df[COL_TASK_NAME].astype(str).str.strip()
    df[COL_TASK_MINUTES] = pd.to_numeric(df[COL_TASK_MINUTES], errors="coerce")
    df = df.dropna(subset=[COL_TASK_DEPT, COL_TASK_NAME, COL_TASK_MINUTES], how="any")
    return df

# ---------------- Dropdown helpers ----------------
def list_departments():
    members = get_members_df()
    return sorted(members[COL_DEPT].dropna().unique().tolist())

def list_members_by_dept(dept: str) -> pd.DataFrame:
    members = get_members_df()
    return members[members[COL_DEPT] == str(dept).strip()].copy()

def list_tasks_by_dept(dept: str) -> pd.DataFrame:
    tasks = get_tasks_df()
    return tasks[tasks[COL_TASK_DEPT] == str(dept).strip()].copy()

# ---------------- Requests ops ----------------
@st.cache_data(ttl=60)
def list_requests(status: str = None) -> pd.DataFrame:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    cols = ["id","name","member_id","date","hours","notes","status",
            "hr_name","hr_notes","created_at","approved_at"]
    df = _ensure_cols(df, cols)
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce")

    # robust sorting by created_at then id
    df["__created_at_dt__"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    if status:
        df = df[df["status"] == status]
    df = df.sort_values(by=["__created_at_dt__", "id"], ascending=[False, False], na_position="last")
    df = df.drop(columns=["__created_at_dt__"])
    return df.reset_index(drop=True)

def append_request_from_selection(dept: str, member_row: pd.Series, task_row: pd.Series, date_str: str) -> int:
    sh = _open_spreadsheet()
    ws = _ensure_requests_sheet(sh)
    df = _read_df(ws)
    cols = ["id","name","member_id","date","hours","notes","status",
            "hr_name","hr_notes","created_at","approved_at"]
    df = _ensure_cols(df, cols)

    name_ar    = str(member_row.get(COL_AR_NAME) or "").strip()
    student_id = _normalize_member_id(member_row.get(COL_STUD_ID))  # ensure normalized
    task_name  = str(task_row.get(COL_TASK_NAME) or "").strip()
    minutes    = float(task_row.get(COL_TASK_MINUTES) or 0.0)
    hours      = round(minutes / 60.0, 2)

    new_row = {
        "id": _new_id(df),
        "name": name_ar,
        "member_id": student_id,
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

    st.cache_data.clear()
    return new_row["id"]

# ---------------- Approved readers (for analytics/rollups) ----------------
@st.cache_data(ttl=60)
def list_approved() -> pd.DataFrame:
    sh = _open_spreadsheet()
    ws = _ensure_approved_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, APPROVED_HEADERS)

    # Normalize types
    df["hours"] = pd.to_numeric(df["hours"], errors="coerce").fillna(0.0)
    df["approved_at_dt"] = pd.to_datetime(df["approved_at"], errors="coerce", utc=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 👇 normalize keys for grouping/merge
    df["member_id"] = df["member_id"].apply(_normalize_member_id)
    df["name"] = df["name"].astype(str).str.strip()

    return df

# ---------------- Meta utilities (period anchor) ----------------
def get_period_anchor() -> pd.Timestamp | None:
    sh = _open_spreadsheet()
    ws = _ensure_meta_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["key","value"])
    row = df.loc[df["key"] == "period_anchor"]
    if row.empty:
        return None
    ts = pd.to_datetime(str(row["value"].iloc[0]), errors="coerce", utc=True)
    return ts if pd.notna(ts) else None

def set_period_anchor_now() -> str:
    """Set anchor to now (UTC ISO seconds) and rebuild period rollup."""
    sh = _open_spreadsheet()
    ws = _ensure_meta_sheet(sh)
    df = _read_df(ws)
    df = _ensure_cols(df, ["key","value"])
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    if (df["key"] == "period_anchor").any():
        df.loc[df["key"] == "period_anchor", "value"] = now_iso
    else:
        df = pd.concat([df, pd.DataFrame([{"key":"period_anchor", "value": now_iso}])], ignore_index=True)
    _write_df(ws, df)
    st.cache_data.clear()
    _rebuild_rollups()  # rebuild after setting anchor
    return now_iso

# ---------------- Rollup builders ----------------
def _build_rollup_df(since_ts_utc: pd.Timestamp | None) -> pd.DataFrame:
    """Aggregate Approved -> per member with join to Member_Data for national_id & dept."""
    app = list_approved()
    if app.empty:
        return pd.DataFrame(columns=LEADER_HEADERS)

    if since_ts_utc is not None:
        app = app[ app["approved_at_dt"] >= since_ts_utc ]
        if app.empty:
            return pd.DataFrame(columns=LEADER_HEADERS)

    # 👇 ensure normalized keys here too (safety)
    app["member_id"] = app["member_id"].apply(_normalize_member_id)
    app["name"] = app["name"].astype(str).str.strip()

    # group per member
    g = (app.groupby(["member_id","name"], dropna=False)
             .agg(total_hours=("hours","sum"),
                  count=("id","count"),
                  last_approved_at=("approved_at_dt","max"))
             .reset_index())
    g["total_hours"] = g["total_hours"].round(2)

    # enrich from Member_Data
    members = get_members_df().copy()
    if COL_NAT_ID not in members.columns:
        members[COL_NAT_ID] = ""
    members_renamed = members.rename(columns={
        COL_AR_NAME: "name",
        COL_STUD_ID: "member_id",
        COL_DEPT: "Department",
        COL_NAT_ID: "national_id",
    })

    # 👇 normalize merge keys on members side
    members_renamed["member_id"] = members_renamed["member_id"].apply(_normalize_member_id)
    members_renamed["name"] = members_renamed["name"].astype(str).str.strip()

    res = g.merge(
        members_renamed[["member_id","name","Department","national_id"]],
        on=["member_id","name"],
        how="left"
    )

    res["Department"] = res["Department"].fillna("")
    res["national_id"] = res["national_id"].fillna("")
    # safe datetime formatting
    res["last_approved_at"] = (
        pd.to_datetime(res["last_approved_at"], utc=True, errors="coerce")
          .dt.tz_convert("UTC")
          .dt.strftime("%Y-%m-%d %H:%M:%S")
          .fillna("")
    )

    # order & sort
    res = res[LEADER_HEADERS]
    res = res.sort_values(["total_hours","count"], ascending=[False, False]).reset_index(drop=True)
    return res

def _rebuild_rollups():
    """Recompute both rollup sheets: all-time & period (since anchor)."""
    sh = _open_spreadsheet()
    # all-time
    lb_ws = _ensure_leaderboard_sheet(sh)
    lb_df = _build_rollup_df(since_ts_utc=None)
    _write_df(lb_ws, lb_df)

    # period (since anchor)
    pr_ws = _ensure_period_sheet(sh)
    anchor = get_period_anchor()
    pr_df = _build_rollup_df(since_ts_utc=anchor)
    _write_df(pr_ws, pr_df)

    st.cache_data.clear()

# ---------------- Approve/Reject with rollups ----------------
def approve_request(target_id: int, hr_name: str, hr_notes: str = "") -> bool:
    """Approve request + upsert into Approved sheet by id, then rebuild rollups."""
    sh = _open_spreadsheet()
    ws_req = _ensure_requests_sheet(sh)
    ws_app = _ensure_approved_sheet(sh)

    # read request row
    req_df = _read_df(ws_req)
    req_df = _ensure_cols(req_df, ["id","name","member_id","date","hours","notes",
                                   "status","hr_name","hr_notes","created_at","approved_at"])
    mask = pd.to_numeric(req_df["id"], errors="coerce").astype("Int64") == int(target_id)
    if not mask.any():
        return False

    approved_at = datetime.utcnow().isoformat(timespec="seconds")
    req_df.loc[mask, "status"]      = "approved"
    req_df.loc[mask, "hr_name"]     = (hr_name or "").strip()
    req_df.loc[mask, "hr_notes"]    = (hr_notes or "").strip()
    req_df.loc[mask, "approved_at"] = approved_at

    # build approved row dict
    row = req_df.loc[mask].iloc[0]
    approved_row = {
        "id":          int(pd.to_numeric(row["id"], errors="coerce")),
        "name":        str(row["name"] or "").strip(),
        "member_id":   str(row["member_id"] or "").strip(),
        "date":        str(row["date"] or "").strip(),
        "hours":       float(pd.to_numeric(row["hours"], errors="coerce") or 0.0),
        "notes":       str(row["notes"] or "").strip(),
        "hr_name":     str(row["hr_name"] or "").strip(),
        "hr_notes":    str(row["hr_notes"] or "").strip(),
        "approved_at": approved_at,
    }

    # upsert Approved
    app_df = _read_df(ws_app)
    app_df = _ensure_cols(app_df, APPROVED_HEADERS)
    app_df["id"] = pd.to_numeric(app_df["id"], errors="coerce").astype("Int64")
    exist_mask = app_df["id"] == int(target_id)
    if exist_mask.any():
        for k, v in approved_row.items():
            app_df.loc[exist_mask, k] = v
    else:
        app_df = pd.concat([app_df, pd.DataFrame([approved_row])], ignore_index=True)

    # write & rebuild rollups
    _write_df(ws_req, req_df)
    _write_df(ws_app, app_df)
    _rebuild_rollups()
    return True

def reject_request(target_id: int, hr_name: str, hr_notes: str = "") -> bool:
    """Reject request + upsert into Rejected sheet by id (does NOT touch Approved)."""
    sh = _open_spreadsheet()
    ws_req = _ensure_requests_sheet(sh)
    ws_rej = _ensure_rejected_sheet(sh)

    req_df = _read_df(ws_req)
    req_df = _ensure_cols(req_df, ["id","name","member_id","date","hours","notes",
                                   "status","hr_name","hr_notes","created_at","approved_at"])
    mask = pd.to_numeric(req_df["id"], errors="coerce").astype("Int64") == int(target_id)
    if not mask.any():
        return False

    # update request row
    req_df.loc[mask, "status"] = "rejected"
    req_df.loc[mask, "hr_name"] = (hr_name or "").strip()
    req_df.loc[mask, "hr_notes"] = (hr_notes or "").strip()
    req_df.loc[mask, "approved_at"] = None

    # build rejected row dict
    rejected_at = datetime.utcnow().isoformat(timespec="seconds")
    row = req_df.loc[mask].iloc[0]
    rejected_row = {
        "id":          int(pd.to_numeric(row["id"], errors="coerce")),
        "name":        str(row["name"] or "").strip(),
        "member_id":   str(row["member_id"] or "").strip(),
        "date":        str(row["date"] or "").strip(),
        "hours":       float(pd.to_numeric(row["hours"], errors="coerce") or 0.0),
        "notes":       str(row["notes"] or "").strip(),
        "hr_name":     (hr_name or "").strip(),
        "hr_notes":    (hr_notes or "").strip(),
        "rejected_at": rejected_at,
    }

    # upsert Rejected
    rej_ws = ws_rej
    rej_df = _read_df(rej_ws)
    rej_df = _ensure_cols(rej_df, REJECTED_HEADERS)
    rej_df["id"] = pd.to_numeric(rej_df["id"], errors="coerce").astype("Int64")
    exist_mask = rej_df["id"] == int(target_id)
    if exist_mask.any():
        for k, v in rejected_row.items():
            rej_df.loc[exist_mask, k] = v
    else:
        rej_df = pd.concat([rej_df, pd.DataFrame([rejected_row])], ignore_index=True)

    _write_df(ws_req, req_df)
    _write_df(rej_ws, rej_df)
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

# ---------------- HR committee helpers ----------------
@st.cache_data(ttl=60)
def list_hr_names() -> list[str]:
    """Return HR committee names for dropdown.
    Priority:
      1) st.secrets['hr']['names'] (list OR comma-separated string)
      2) Members whose Department ∈ {HR, Human Resources, الموارد البشرية} from Member_Data
    """
    # 1) try secrets
    try:
        if "hr" in st.secrets and "names" in st.secrets["hr"]:
            raw = st.secrets["hr"]["names"]
            if isinstance(raw, (list, tuple)):
                names = [str(x).strip() for x in raw if str(x).strip()]
            else:
                names = [s.strip() for s in str(raw).split(",") if s.strip()]
            if names:
                return sorted(set(names))
    except Exception:
        pass

    # 2) fallback to Member_Data by department
    try:
        df = get_members_df()
        if not df.empty and COL_DEPT in df.columns and COL_AR_NAME in df.columns:
            hr_aliases = {"HR", "Human Resources", "الموارد البشرية"}
            aliases_ci = {a.casefold() for a in hr_aliases}
            dept_ci = df[COL_DEPT].astype(str).str.strip().str.casefold()
            mask = dept_ci.isin(aliases_ci)
            names = (
                df.loc[mask, COL_AR_NAME]
                .dropna()
                .astype(str)
                .str.strip()
                .tolist()
            )
            names = [n for n in names if n]
            if names:
                return sorted(set(names))
    except Exception:
        pass

    return []
