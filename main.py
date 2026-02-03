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
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1bRXFLHiSsYVpofyXSf2UUcAsO_gM37aHsUv0CogmfPI/edit?gid=0#gid=0"
    return gc.open_by_url(SPREADSHEET_URL)

sh = get_ss_connection()
ws_main = sh.get_worksheet(0)
CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAAAD-bZDK4/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=gK0I12cncnoO_AzBlSfLtoOrIH1v-mKINo1Iah0OTbw"

def get_staff_list():
    try:
        ws_staff = sh.worksheet("担当者マスタ")
        return ws_staff.col_values(1)[1:]
    except:
        return ["担当者不明"]

staff_list = get_staff_list()
status_options = ["受付", "対応中", "保留中", "完了"]
job_options = ["修繕", "管理", "その他"]

st.title("🏢 総務部 業務管理システム")
tab_today, tab_input, tab_search = st.tabs(["📅 本日のタスク", "📝 新規登録", "🔍 一覧・検索・編集"])

# --- 【タブ1】本日のタスク ---
with tab_today:
    st.subheader("🚩 本日の未完了タスク")
    all_data = ws_main.get_all_records()
    df_all = pd.DataFrame(all_data)
    if not df_all.empty:
        today_str = datetime.datetime.now(JST).strftime("%Y/%m/%d")
        df_today = df_all[(df_all["発生日"] == today_str) & (df_all["ステータス"] != "完了")]
        st.dataframe(df_today, use_container_width=True)
    else:
        st.info("データがありません。")

# --- 【タブ2】新規登録 ---
with tab_input:
    st.subheader("新規タスク登録")
    with st.form("input_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            i_job = st.selectbox("業務種別", job_options, key="i_job")
            i_title = st.text_input("案件名（必須）")
            i_loc = st.text_input("場所")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1: i_dept = st.text_input("依頼部署")
            with sub_c2: i_req = st.text_input("依頼者")
        with c2:
            i_staff = st.selectbox("担当者", staff_list, key="i_staff")
            now_jst = datetime.datetime.now(JST)
            i_date = st.date_input("対応開始日", value=now_jst.date())
            i_time = st.time_input("対応開始時間", value=now_jst.time())
        i_content = st.text_area("対応内容", height=200)
        i_memo = st.text_area("メモ", height=150)
        
        if st.form_submit_button("新規登録"):
            if i_title:
                dt_str = datetime.datetime.combine(i_date, i_time).strftime("%Y/%m/%d %H:%M")
                new_row = [now_jst.strftime("%Y/%m/%d"), i_job, "受付", i_title, i_content, i_loc, i_dept, i_req, i_staff, dt_str, "", i_memo]
                ws_main.append_row(new_row)
                st.success("登録完了！")
                st.rerun()

# --- 【タブ3】一覧・検索・編集 ---
with tab_search:
    st.subheader("🔍 タスク一覧・選択")
    all_data_edit = ws_main.get_all_records()
    df_raw = pd.DataFrame(all_data_edit)
    
    if not df_raw.empty:
        search_kw = st.text_input("キーワード検索")
        df_filtered = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains(search_kw).any(), axis=1)].copy() if search_kw else df_raw.copy()
        df_filtered["row_no"] = df_filtered.index + 2
        df_filtered.insert(0, "選択", False)

        edited_df = st.data_editor(
            df_filtered.drop(columns=["row_no"]),
            hide_index=True,
            column_config={"選択": st.column_config.CheckboxColumn("選択", default=False)},
            disabled=[col for col in df_filtered.columns if col != "選択"],
            key="data_editor", use_container_width=True
        )

        selected_indices = edited_df.index[edited_df["選択"] == True].tolist()

        if selected_indices:
            target_idx = selected_indices[-1]
            row_idx = df_filtered.loc[target_idx, "row_no"]
            curr = df_filtered.loc[target_idx]

            st.divider()
            with st.form("edit_form"):
                st.subheader(f"📝 編集: {curr['案件名']}")
                e1, e2 = st.columns(2)
                
                # --- 日時文字列をパースする補助関数 ---
                def parse_dt(dt_str):
                    try: return datetime.datetime.strptime(dt_str, "%Y/%m/%d %H:%M")
                    except: return datetime.datetime.now(JST)

                with e1:
                    e_status = st.selectbox("ステータス", status_options, index=status_options.index(curr["ステータス"]) if curr["ステータス"] in status_options else 0)
                    e_type = st.selectbox("業務種別", job_options, index=job_options.index(curr["業務種別"]) if curr["業務種別"] in job_options else 0)
                    e_title = st.text_input("案件名", value=curr["案件名"])
                    e_loc = st.text_input("場所", value=curr["場所"])
                    
                    st.write("🕒 **対応開始日時**")
                    start_dt = parse_dt(curr["対応開始日時"])
                    c_sd1, c_sd2 = st.columns(2)
                    e_sd = c_sd1.date_input("開始日", value=start_dt.date())
                    e_st = c_sd2.time_input("開始時間", value=start_dt.time())

                with e2:
                    e_staff = st.selectbox("担当者", staff_list, index=staff_list.index(curr["担当者"]) if curr["担当者"] in staff_list else 0)
                    e_dept = st.text_input("依頼部署", value=curr["依頼部署"])
                    e_req = st.text_input("依頼者", value=curr["依頼者"])
                    
                    st.write("📅 **発生日**")
                    try: occ_date = datetime.datetime.strptime(curr["発生日"], "%Y/%m/%d").date()
                    except: occ_date = datetime.date.today()
                    e_occ_date = st.date_input("発生日選択", value=occ_date)

                    st.write("🏁 **完了日時**")
                    end_dt = parse_dt(curr["完了日時"]) if curr["完了日時"] else None
                    c_ed1, c_ed2 = st.columns(2)
                    e_ed = c_ed1.date_input("完了日", value=end_dt.date() if end_dt else datetime.date.today())
                    e_et = c_ed2.time_input("完了時間", value=end_dt.time() if end_dt else datetime.time(0, 0))
                
                e_content = st.text_area("対応内容", value=curr["対応内容"], height=200)
                e_memo = st.text_area("メモ", value=curr["メモ"], height=100)
                set_now = st.checkbox("今すぐ完了にする（完了日時に現在時刻を入力）")
                
                if st.form_submit_button("💾 変更をすべて保存"):
                    # 入力された日付と時間を合体させる
                    final_start_str = datetime.datetime.combine(e_sd, e_st).strftime("%Y/%m/%d %H:%M")
                    
                    if set_now:
                        final_status = "完了"
                        final_end_str = datetime.datetime.now(JST).strftime("%Y/%m/%d %H:%M")
                    else:
                        final_status = e_status
                        # 完了日時が未入力（デフォルトの状態）なら空文字、入力があればその値
                        if curr["完了日時"] == "" and not set_now and e_ed == datetime.date.today() and e_et == datetime.time(0, 0):
                            final_end_str = ""
                        else:
                            final_end_str = datetime.datetime.combine(e_ed, e_et).strftime("%Y/%m/%d %H:%M")
                    
                    final_occ_str = e_occ_date.strftime("%Y/%m/%d")
                    
                    # スプレッドシート A~L列
                    updated = [final_occ_str, e_type, final_status, e_title, e_content, e_loc, e_dept, e_req, e_staff, final_start_str, final_end_str, e_memo]
                    ws_main.update(range_name=f"A{row_idx}:L{row_idx}", values=[updated])
                    st.success("スプレッドシートを更新しました！")
                    st.rerun()
        else:
            st.warning("編集したいタスクを上の表から選択してください。")
