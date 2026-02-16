import streamlit as st
import gspread
import pandas as pd
import datetime
from datetime import timezone, timedelta
import requests
import json
from google.oauth2.credentials import Credentials

# 日本時間(JST)の定義
JST = timezone(timedelta(hours=+9))

# ページの設定
st.set_page_config(page_title="総務部タスク管理システム", layout="wide")

# --- 認証とスプレッドシートの取得 ---
@st.cache_resource
def get_ss_connection():
    authorized_user_info = json.loads(st.secrets["gcp_authorized_user"])
    creds = Credentials.from_authorized_user_info(authorized_user_info)
    gc = gspread.authorize(creds)
    # ★スプレッドシートのURL
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1bRXFLHiSsYVpofyXSf2UUcAsO_gM37aHsUv0CogmfPI/edit?gid=0#gid=0"
    return gc.open_by_url(SPREADSHEET_URL)

sh = get_ss_connection()
ws_main = sh.get_worksheet(0)

# --- 通知設定 (新しいURLに更新済み) ---
CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAQAjLROc5M/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=ePbMJg9ty_XhCBzDsF1M47VEmGHF24ZoJNG5QVGTV5M"
APP_URL = "https://soumu-task-management-efzwxzn7qf9hqznyev64vu.streamlit.app/"

def send_chat_notification(text):
    if "http" in CHAT_WEBHOOK_URL:
        full_text = f"{text}\n\n🔗 確認はコチラ：\n{APP_URL}"
        try:
            requests.post(CHAT_WEBHOOK_URL, json={"text": full_text})
        except: pass

def get_staff_list():
    try:
        ws_staff = sh.worksheet("担当者マスタ")
        return ws_staff.col_values(1)[1:]
    except: return ["担当者不明"]

staff_list = get_staff_list()
status_options = ["受付", "対応中", "保留中", "完了"]
job_options = ["修繕", "管理", "その他"]

# --- 表示用カラム設定 (共通) ---
COL_CONFIG = {
    "内容": st.column_config.TextColumn("内容", width="large"),
    "原因": st.column_config.TextColumn("原因", width="large"),
    "対処": st.column_config.TextColumn("対処", width="large"),
    "メモ": st.column_config.TextColumn("メモ", width="large"),
    "写真URL": st.column_config.LinkColumn("写真URL", width="medium"),
}

st.title("🏢 総務部 業務管理システム")
tab_today, tab_input, tab_search = st.tabs(["📅 本日のタスク", "📝 新規登録", "🔍 一覧・検索・編集"])

# --- 【タブ1】本日のタスク ---
with tab_today:
    st.subheader("🚩 現在対応中のタスク一覧")
    all_data = ws_main.get_all_records()
    df_all = pd.DataFrame(all_data)
    
    if not df_all.empty:
        df_todo = df_all[df_all["ステータス"] != "完了"].copy()
        if not df_todo.empty:
            df_todo = df_todo.sort_values("発生日", ascending=False)
            st.dataframe(df_todo, use_container_width=True, column_config=COL_CONFIG, height=400)
        else:
            st.info("現在、未完了のタスクはありません。")
    else:
        st.info("データがありません。")

# --- 【タブ2】新規登録 ---
with tab_input:
    st.subheader("新規タスク登録")
    with st.form("input_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            i_job = st.selectbox("業務種別", job_options)
            i_status = st.selectbox("ステータス", status_options)
            i_title = st.text_input("案件名（必須）")
            i_loc = st.text_input("場所")
        with c2:
            i_staff = st.selectbox("担当者", staff_list)
            i_dept = st.text_input("依頼部署")
            i_req = st.text_input("依頼者")
            now_jst = datetime.datetime.now(JST)
            ic1, ic2 = st.columns(2)
            i_date = ic1.date_input("開始日", value=now_jst.date())
            i_time = ic2.time_input("開始時間", value=now_jst.time())
        
        i_content = st.text_area("内容", height=100)
        i_cause = st.text_area("原因", height=100)
        i_action = st.text_area("対処", height=100)
        i_photo = st.text_input("写真URL (Googleドライブのリンク)")
        i_memo = st.text_area("メモ", height=100)
        
        if st.form_submit_button("新規登録"):
            if i_title:
                dt_str = datetime.datetime.combine(i_date, i_time).strftime("%Y/%m/%d %H:%M")
                new_row = [
                    now_jst.strftime("%Y/%m/%d"), i_job, i_status, i_title, 
                    i_content, i_cause, i_action, 
                    i_loc, i_dept, i_req, i_staff, dt_str, "", i_memo, i_photo
                ]
                ws_main.append_row(new_row)
                send_chat_notification(f"📢 **【新規登録】**\n案件: {i_title}\n担当: {i_staff}")
                st.success("登録完了！")
                st.rerun()

# --- 【タブ3】一覧・検索・編集 ---
with tab_search:
    st.subheader("🔍 タスク一覧・検索")
    c_srch1, c_srch2 = st.columns([8, 1])
    search_kw = c_srch1.text_input("検索ワード", label_visibility="collapsed")
    btn_search = c_srch2.button("🔍 検索")

    all_data_edit = ws_main.get_all_records()
    df_raw = pd.DataFrame(all_data_edit)
    
    if not df_raw.empty:
        df_filtered = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains(search_kw).any(), axis=1)].copy() if search_kw else df_raw.copy()
        df_filtered["row_no"] = df_filtered.index + 2
        df_filtered.insert(0, "選択", False)

        EDIT_COL_CONFIG = COL_CONFIG.copy()
        EDIT_COL_CONFIG["選択"] = st.column_config.CheckboxColumn("選択", default=False)

        edited_df = st.data_editor(
            df_filtered.drop(columns=["row_no"]),
            hide_index=True,
            column_config=EDIT_COL_CONFIG,
            disabled=[col for col in df_filtered.columns if col != "選択"],
            key="data_editor", 
            use_container_width=True,
            height=500 
        )

        selected_indices = edited_df.index[edited_df["選択"] == True].tolist()

        if selected_indices:
            target_idx = selected_indices[-1]
            row_idx = df_filtered.loc[target_idx, "row_no"]
            curr = df_filtered.loc[target_idx]

            st.divider()
            
            del_c1, del_c2 = st.columns([6, 1])
            with del_c2:
                confirm_delete = st.checkbox("削除有効化")
                if st.button("🚨 完全に削除", disabled=not confirm_delete):
                    ws_main.delete_rows(int(row_idx))
                    st.warning("削除しました。")
                    st.rerun()

            with st.form("edit_form"):
                st.markdown(f"### 📝 編集: {curr['案件名']}")
                ec1, ec2, ec3 = st.columns(3)
                with ec1: e_status = st.selectbox("ステータス", status_options, index=status_options.index(curr["ステータス"]) if curr["ステータス"] in status_options else 0)
                with ec2: e_type = st.selectbox("業務種別", job_options, index=job_options.index(curr["業務種別"]) if curr["業務種別"] in job_options else 0)
                with ec3: e_staff = st.selectbox("担当者", staff_list, index=staff_list.index(curr["担当者"]) if curr["担当者"] in staff_list else 0)
                
                e_title = st.text_input("案件名", value=curr["案件名"])
                
                ec4, ec5, ec6 = st.columns(3)
                with ec4: e_loc = st.text_input("場所", value=curr["場所"])
                with ec5: e_dept = st.text_input("依頼部署", value=curr["依頼部署"])
                with ec6: e_req = st.text_input("依頼者", value=curr["依頼者"])

                st.write("---")
                st.markdown("##### ⏰ 日時設定")
                
                def safe_parse_dt(val):
                    if not val or pd.isna(val): return None
                    for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
                        try: return datetime.datetime.strptime(str(val), fmt)
                        except: continue
                    return None

                occ_dt = safe_parse_dt(curr["発生日"])
                e_occ_date = st.date_input("発生日", value=occ_dt.date() if occ_dt else datetime.date.today())

                st.write("**対応開始日時**")
                s_dt = safe_parse_dt(curr["対応開始日時"])
                cs1, cs2, cs3 = st.columns([2, 2, 3])
                e_sd = cs1.date_input("開始日", value=s_dt.date() if s_dt else datetime.date.today(), label_visibility="collapsed", key="esd")
                e_st = cs2.time_input("開始時", value=s_dt.time() if (s_dt and ":" in str(curr["対応開始日時"])) else datetime.time(9, 0), label_visibility="collapsed", key="est")
                s_mode = cs3.radio("開始形式", ["日付+時刻", "日付のみ", "空欄"], index=0 if (s_dt and ":" in str(curr["対応開始日時"])) else (1 if s_dt else 2), horizontal=True, label_visibility="collapsed", key="smode")

                st.write("**完了日時**")
                e_dt = safe_parse_dt(curr["完了日時"])
                ce1, ce2, ce3 = st.columns([2, 2, 3])
                e_ed = ce1.date_input("完了日", value=e_dt.date() if e_dt else datetime.date.today(), label_visibility="collapsed", key="eed")
                e_et = ce2.time_input("完了時", value=e_dt.time() if (e_dt and ":" in str(curr["完了日時"])) else datetime.time(17, 0), label_visibility="collapsed", key="eet")
                e_mode = ce3.radio("完了形式", ["日付+時刻", "日付のみ", "空欄"], index=0 if (e_dt and ":" in str(curr["完了日時"])) else (1 if e_dt else 2), horizontal=True, label_visibility="collapsed", key="emode")

                st.write("---")
                e_content = st.text_area("内容", value=curr.get("内容", ""))
                e_cause = st.text_area("原因", value=curr.get("原因", ""))
                e_action = st.text_area("対処", value=curr.get("対処", ""))
                
                e_photo = st.text_input("写真URL (Googleドライブのリンク)", value=curr.get("写真URL", ""))
                if e_photo:
                    st.link_button("🖼 現場写真を表示（別タブで開く）", e_photo)
                
                e_memo = st.text_area("メモ", value=curr.get("メモ", ""))
                do_notify = st.checkbox("通知する", value=False)

                if st.form_submit_button("💾 保存"):
                    fs = datetime.datetime.combine(e_sd, e_st).strftime("%Y/%m/%d %H:%M") if s_mode == "日付+時刻" else (e_sd.strftime("%Y/%m/%d") if s_mode == "日付のみ" else "")
                    fe = datetime.datetime.combine(e_ed, e_et).strftime("%Y/%m/%d %H:%M") if e_mode == "日付+時刻" else (e_ed.strftime("%Y/%m/%d") if e_mode == "日付のみ" else "")
                    
                    updated_row = [
                        e_occ_date.strftime("%Y/%m/%d"), e_type, e_status, e_title, 
                        e_content, e_cause, e_action, 
                        e_loc, e_dept, e_req, e_staff, fs, fe, e_memo, e_photo
                    ]
                    ws_main.update(range_name=f"A{row_idx}:O{row_idx}", values=[updated_row])
                    if do_notify: send_chat_notification(f"📝 **更新**: {e_title}")
                    st.success("更新しました！")
                    st.rerun()
