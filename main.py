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

@st.cache_resource
def get_ss_connection():
    authorized_user_info = json.loads(st.secrets["gcp_authorized_user"])
    creds = Credentials.from_authorized_user_info(authorized_user_info)
    gc = gspread.authorize(creds)
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1bRXFLHiSsYVpofyXSf2UUcAsO_gM37aHsUv0CogmfPI/edit?gid=0#gid=0"
    return gc.open_by_url(SPREADSHEET_URL)

sh = get_ss_connection()
ws_main = sh.get_worksheet(0)

# --- Google Chat Webhook URL ---
CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAAAD-bZDK4/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=gK0I12cncnoO_AzBlSfLtoOrIH1v-mKINo1Iah0OTbw"

def send_chat_notification(text):
    if "http" in CHAT_WEBHOOK_URL:
        try:
            requests.post(CHAT_WEBHOOK_URL, json={"text": text})
        except Exception as e:
            st.error(f"通知送信エラー: {e}")

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
            sc1, sc2 = st.columns(2)
            i_dept = sc1.text_input("依頼部署")
            i_req = sc2.text_input("依頼者")
        with c2:
            i_staff = st.selectbox("担当者", staff_list, key="i_staff")
            now_jst = datetime.datetime.now(JST)
            i_date = st.date_input("対応開始日", value=now_jst.date())
            i_time = st.time_input("対応開始時間", value=now_jst.time())
        i_content = st.text_area("対応内容", height=200)
        i_memo = st.text_area("メモ", height=100)
        
        if st.form_submit_button("新規登録"):
            if i_title:
                dt_str = datetime.datetime.combine(i_date, i_time).strftime("%Y/%m/%d %H:%M")
                new_row = [now_jst.strftime("%Y/%m/%d"), i_job, "受付", i_title, i_content, i_loc, i_dept, i_req, i_staff, dt_str, "", i_memo]
                ws_main.append_row(new_row)
                send_chat_notification(f"📢 **【新規タスク登録】**\n案件: {i_title}\n担当: {i_staff}")
                st.success("登録完了！")
                st.rerun()

# --- 【タブ3】一覧・検索・編集 ---
with tab_search:
    st.subheader("🔍 タスク一覧・検索")
    
    # --- 虫眼鏡ボタン付き検索欄 ---
    c_srch1, c_srch2 = st.columns([8, 1])
    search_kw = c_srch1.text_input("検索ワードを入力", key="srch_val", label_visibility="collapsed")
    btn_search = c_srch2.button("🔍 検索")

    all_data_edit = ws_main.get_all_records()
    df_raw = pd.DataFrame(all_data_edit)
    
    if not df_raw.empty:
        # 検索処理
        if search_kw:
            df_filtered = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains(search_kw).any(), axis=1)].copy()
        else:
            df_filtered = df_raw.copy()

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
                st.markdown(f"### 📝 編集: {curr['案件名']}")
                
                c1, c2, c3 = st.columns(3)
                with c1: e_status = st.selectbox("ステータス", status_options, index=status_options.index(curr["ステータス"]) if curr["ステータス"] in status_options else 0)
                with c2: e_type = st.selectbox("業務種別", job_options, index=job_options.index(curr["業務種別"]) if curr["業務種別"] in job_options else 0)
                with c3: e_staff = st.selectbox("担当者", staff_list, index=staff_list.index(curr["担当者"]) if curr["担当者"] in staff_list else 0)
                
                e_title = st.text_input("案件名", value=curr["案件名"])
                
                c4, c5, c6 = st.columns(3)
                with c4: e_loc = st.text_input("場所", value=curr["場所"])
                with c5: e_dept = st.text_input("依頼部署", value=curr["依頼部署"])
                with c6: e_req = st.text_input("依頼者", value=curr["依頼者"])

                st.markdown("##### ⏰ 日時設定")
                def get_dt_obj(val):
                    try: return datetime.datetime.strptime(str(val), "%Y/%m/%d %H:%M")
                    except: 
                        try: return datetime.datetime.strptime(str(val), "%Y/%m/%d")
                        except: return None

                # 発生日
                try: occ_d = datetime.datetime.strptime(str(curr["発生日"]), "%Y/%m/%d").date()
                except: occ_d = datetime.date.today()
                e_occ_date = st.date_input("発生日", value=occ_d)

                # --- レイアウトをピシッと整列させる工夫 ---
                # 開始日時
                st.write("**対応開始日時**")
                start_dt = get_dt_obj(curr["対応開始日時"])
                cs_1, cs_2, cs_3 = st.columns([1, 1, 1])
                e_sd = cs_1.date_input("開始日", value=start_dt.date() if start_dt else datetime.date.today(), key="esd_v")
                e_st = cs_2.time_input("開始時", value=start_dt.time() if (start_dt and ":" in str(curr["対応開始日時"])) else datetime.time(9, 0), key="est_v")
                s_mode = cs_3.radio("開始保存形式", ["日付+時刻", "日付のみ", "空欄"], index=0 if start_dt else 2, key="sm_v", horizontal=True)

                # 完了日時
                st.write("**完了日時**")
                end_dt = get_dt_obj(curr["完了日時"])
                ce_1, ce_2, ce_3 = st.columns([1, 1, 1])
                e_ed = ce_1.date_input("完了日", value=end_dt.date() if end_dt else datetime.date.today(), key="eed_v")
                e_et = ce_2.time_input("完了時", value=end_dt.time() if (end_dt and ":" in str(curr["完了日時"])) else datetime.time(17, 0), key="eet_v")
                e_mode = ce_3.radio("完了保存形式", ["日付+時刻", "日付のみ", "空欄"], index=0 if end_dt else 2, key="em_v", horizontal=True)

                st.write("---")
                e_content = st.text_area("対応内容", value=curr["対応内容"], height=150)
                e_memo = st.text_area("メモ", value=curr["メモ"], height=100)
                
                do_notify = st.checkbox("更新をチャットに通知する")

                if st.form_submit_button("💾 変更をすべて保存"):
                    # 文字列化ロジック
                    fs = datetime.datetime.combine(e_sd, e_st).strftime("%Y/%m/%d %H:%M") if s_mode == "日付+時刻" else (e_sd.strftime("%Y/%m/%d") if s_mode == "日付のみ" else "")
                    fe = datetime.datetime.combine(e_ed, e_et).strftime("%Y/%m/%d %H:%M") if e_mode == "日付+時刻" else (e_ed.strftime("%Y/%m/%d") if e_mode == "日付のみ" else "")
                    
                    updated = [e_occ_date.strftime("%Y/%m/%d"), e_type, e_status, e_title, e_content, e_loc, e_dept, e_req, e_staff, fs, fe, e_memo]
                    ws_main.update(range_name=f"A{row_idx}:L{row_idx}", values=[updated])
                    if do_notify: send_chat_notification(f"📝 **【タスク更新】**\n案件: {e_title}\n状態: {e_status}")
                    st.success("更新完了！")
                    st.rerun()
