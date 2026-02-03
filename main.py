import streamlit as st
import gspread
import pandas as pd
import datetime
import requests
import json
from google.oauth2.credentials import Credentials

# ページの設定
st.set_page_config(page_title="総務部タスク管理システム", layout="wide")

# --- 認証とスプレッドシートの取得（サーバー Secrets対応版） ---
@st.cache_resource
def get_ss_connection():
    # Secretsから認証情報を読み込む
    authorized_user_info = json.loads(st.secrets["gcp_authorized_user"])
    
    # ファイルを使わずに直接認証オブジェクトを作成
    creds = Credentials.from_authorized_user_info(authorized_user_info)
    gc = gspread.authorize(creds)
    
    # スプレッドシートのURL
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1bRXFLHiSsYVpofyXSf2UUcAsO_gM37aHsUv0CogmfPI/edit?gid=0#gid=0"
    return gc.open_by_url(SPREADSHEET_URL)

# --- 初期接続設定 ---
sh = get_ss_connection()
ws_main = sh.get_worksheet(0)

# ★Google ChatのWebhook URL
CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAAAD-bZDK4/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=gK0I12cncnoO_AzBlSfLtoOrIH1v-mKINo1Iah0OTbw"

# --- マスタデータ取得 ---
def get_staff_list():
    try:
        ws_staff = sh.worksheet("担当者マスタ")
        return ws_staff.col_values(1)[1:]
    except:
        return ["担当者不明"]

staff_list = get_staff_list()
status_options = ["受付", "対応中", "保留中", "完了"]
job_options = ["修繕", "管理", "その他"]

# --- メイン画面 ---
st.title("🏢 総務部 業務管理システム")
tab_today, tab_input, tab_search = st.tabs(["📅 本日のタスク", "📝 新規登録", "🔍 一覧・検索・編集"])

# --- 【タブ1】本日のタスク ---
with tab_today:
    st.subheader("🚩 本日の未完了タスク")
    all_data = ws_main.get_all_records()
    df_all = pd.DataFrame(all_data)
    if not df_all.empty:
        today_str = datetime.date.today().strftime("%Y/%m/%d")
        # フィルタリング
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
            now = datetime.datetime.now()
            i_date = st.date_input("対応開始日", value=now.date())
            i_time = st.time_input("対応開始時間", value=now.time())
        
        i_content = st.text_area("対応内容", height=200)
        i_memo = st.text_area("メモ", height=150)
        
        if st.form_submit_button("新規登録"):
            if i_title:
                dt_str = datetime.datetime.combine(i_date, i_time).strftime("%Y/%m/%d %H:%M")
                new_row = [datetime.date.today().strftime("%Y/%m/%d"), i_job, "受付", i_title, i_content, i_loc, i_dept, i_req, i_staff, dt_str, "", i_memo]
                ws_main.append_row(new_row)
                
                # --- チャット通知処理 ---
                if "http" in CHAT_WEBHOOK_URL:
                    msg = {
                        "text": f"📢 **【新規タスク登録】**\n--------------------------------\n🔹**案件名**: {i_title}\n🔹**種別**: {i_job}\n🔹**担当者**: {i_staff}\n🔹**場所**: {i_loc}\n--------------------------------"
                    }
                    try:
                        requests.post(CHAT_WEBHOOK_URL, json=msg)
                    except Exception as e:
                        st.error(f"通知送信エラー: {e}")
                
                st.success("登録完了！チャットへ通知しました。")
                st.rerun()
            else:
                st.error("案件名は必須です。")

# --- 【タブ3】一覧・検索・編集 ---
with tab_search:
    st.subheader("🔍 タスク一覧・選択")
    all_data_edit = ws_main.get_all_records()
    df_raw = pd.DataFrame(all_data_edit)
    
    if not df_raw.empty:
        search_kw = st.text_input("キーワード検索（全項目対象）")
        if search_kw:
            mask = df_raw.apply(lambda row: row.astype(str).str.contains(search_kw).any(), axis=1)
            df_filtered = df_raw[mask].copy()
        else:
            df_filtered = df_raw.copy()

        df_filtered["row_no"] = df_filtered.index + 2
        df_filtered.insert(0, "選択", False)

        edited_df = st.data_editor(
            df_filtered.drop(columns=["row_no"]),
            hide_index=True,
            column_config={"選択": st.column_config.CheckboxColumn("選択", default=False)},
            disabled=[col for col in df_filtered.columns if col != "選択"],
            key="data_editor", use_container_width=True, height=300
        )

        selected_indices = edited_df.index[edited_df["選択"] == True].tolist()

        if selected_indices:
            target_idx = selected_indices[-1]
            row_idx = df_filtered.loc[target_idx, "row_no"]
            curr = df_filtered.loc[target_idx]

            st.divider()
            st.subheader(f"📝 編集中のタスク: {curr['案件名']}")
            now_dt = datetime.datetime.now()

            with st.form("edit_form"):
                e1, e2 = st.columns(2)
                with e1:
                    st.text_input("ステータス", value=curr["ステータス"], disabled=True)
                    e_type = st.selectbox("業務種別", job_options, index=job_options.index(curr["業務種別"]) if curr["業務種別"] in job_options else 0)
                    e_title = st.text_input("案件名", value=curr["案件名"])
                    e_loc = st.text_input("場所", value=curr["場所"])
                    st.write("🕒 **対応開始日時**")
                    ec1, ec2 = st.columns(2)
                    try: d_start = datetime.datetime.strptime(curr["対応開始日時"], "%Y/%m/%d %H:%M")
                    except: d_start = now_dt
                    e_start_date = ec1.date_input("開始日", value=d_start.date(), key="edit_sd")
                    e_start_time = ec2.time_input("開始時間", value=d_start.time(), key="edit_st")
                with e2:
                    e_staff = st.selectbox("担当者", staff_list, index=staff_list.index(curr["担当er"]) if curr["担当者"] in staff_list else 0)
                    es_col1, es_col2 = st.columns(2)
                    with es_col1: e_dept = st.text_input("依頼部署", value=curr["依頼部署"])
                    with es_col2: e_req = st.text_input("依頼者", value=curr["依頼者"])
                    st.write("🏁 **完了日時**")
                    set_now = st.checkbox("完了日時に現在時刻をセットする")
                    ec3, ec4 = st.columns(2)
                    try: d_end_base = datetime.datetime.strptime(curr["完了日時"], "%Y/%m/%d %H:%M") if curr["完了日時"] else now_dt
                    except: d_end_base = now_dt
                    f_d_end = now_dt.date() if set_now else d_end_base.date()
                    f_t_end = now_dt.time() if set_now else d_end_base.time()
                    e_end_date = ec3.date_input("完了日", value=f_d_end, key="edit_ed")
                    e_end_time = ec4.time_input("完了時間", value=f_t_end, key="edit_et")
                
                e_content = st.text_area("対応内容", value=curr["対応内容"], height=350)
                e_memo = st.text_area("メモ", value=curr["メモ"], height=150)

                if st.form_submit_button("💾 全項目を確定して更新"):
                    final_start_str = datetime.datetime.combine(e_start_date, e_start_time).strftime("%Y/%m/%d %H:%M")
                    final_end_str = datetime.datetime.combine(e_end_date, e_end_time).strftime("%Y/%m/%d %H:%M")
                    new_status = "完了" if set_now else curr["ステータス"]
                    if not set_now and curr["完了日時"] == "": final_end_str = ""
                    
                    updated = [curr["発生日"], e_type, new_status, e_title, e_content, e_loc, e_dept, e_req, e_staff, final_start_str, final_end_str, e_memo]
                    ws_main.update(range_name=f"A{row_idx}:L{row_idx}", values=[updated])
                    st.success("更新しました！")
                    st.rerun()
        else:
            st.warning("⚠️ 編集したいタスクを上の表から1つ選んでください。")
    else:
        st.info("データがありません。")
