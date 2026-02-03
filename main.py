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
        i_memo = st.text_area("メモ", height=100)
        
        if st.form_submit_button("新規登録"):
            if i_title:
                dt_str = datetime.datetime.combine(i_date, i_time).strftime("%Y/%m/%d %H:%M")
                new_row = [now_jst.strftime("%Y/%m/%d"), i_job, "受付", i_title, i_content, i_loc, i_dept, i_req, i_staff, dt_str, "", i_memo]
                ws_main.append_row(new_row)
                st.success("登録完了！")
                st.rerun()

# --- 【タブ3】一覧・検索・編集 ---
with tab_search:
    st.subheader("🔍 タスク一覧・検索")
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
                st.markdown(f"### 📝 編集: {curr['案件名']}")
                
                # --- セクション1: 基本情報 ---
                st.markdown("##### ⚙️ 基本・担当情報")
                c1, c2, c3 = st.columns(3)
                with c1: e_status = st.selectbox("ステータス", status_options, index=status_options.index(curr["ステータス"]) if curr["ステータス"] in status_options else 0)
                with c2: e_type = st.selectbox("業務種別", job_options, index=job_options.index(curr["業務種別"]) if curr["業務種別"] in job_options else 0)
                with c3: e_staff = st.selectbox("担当者", staff_list, index=staff_list.index(curr["担当者"]) if curr["担当者"] in staff_list else 0)
                
                e_title = st.text_input("案件名", value=curr["案件名"])
                
                # --- セクション2: 依頼詳細 ---
                st.markdown("##### 📍 依頼詳細")
                c4, c5, c6 = st.columns(3)
                with c4: e_loc = st.text_input("場所", value=curr["場所"])
                with c5: e_dept = st.text_input("依頼部署", value=curr["依頼部署"])
                with c6: e_req = st.text_input("依頼者", value=curr["依頼者"])

                # --- セクション3: 日時設定 ---
                st.markdown("##### ⏰ 日時設定（時刻を空にする場合はチェックを外す）")
                
                def parse_dt(dt_str):
                    try: return datetime.datetime.strptime(dt_str, "%Y/%m/%d %H:%M")
                    except: return None

                # 発生日
                try: occ_d = datetime.datetime.strptime(curr["発生日"], "%Y/%m/%d").date()
                except: occ_d = datetime.date.today()
                
                # レイアウトを整列させるためのカラム
                col_occ, col_start, col_end = st.columns([1, 2, 2])
                
                with col_occ:
                    e_occ_date = st.date_input("発生日", value=occ_d)

                with col_start:
                    start_dt = parse_dt(curr["対応開始日時"])
                    st.write("対応開始日時")
                    cs1, cs2, cs3 = st.columns([1.5, 1.5, 1])
                    use_start_time = cs3.checkbox("時刻", value=True if start_dt else False, key="u_st")
                    e_sd = cs1.date_input("開始日", value=start_dt.date() if start_dt else datetime.date.today(), label_visibility="collapsed")
                    e_st = cs2.time_input("開始時", value=start_dt.time() if start_dt else datetime.time(9, 0), label_visibility="collapsed", disabled=not use_start_time)
                
                with col_end:
                    end_dt = parse_dt(curr["完了日時"])
                    st.write("完了日時")
                    ce1, ce2, ce3 = st.columns([1.5, 1.5, 1])
                    use_end_time = ce3.checkbox("時刻", value=True if end_dt else False, key="u_et")
                    e_ed = ce1.date_input("完了日", value=end_dt.date() if end_dt else datetime.date.today(), label_visibility="collapsed")
                    e_et = ce2.time_input("完了時", value=end_dt.time() if end_dt else datetime.time(17, 0), label_visibility="collapsed", disabled=not use_end_time)

                # --- セクション4: 内容とメモ ---
                st.markdown("##### 📝 内容詳細")
                e_content = st.text_area("対応内容", value=curr["対応内容"], height=150)
                e_memo = st.text_area("メモ", value=curr["メモ"], height=100)
                
                if st.form_submit_button("💾 変更をすべて保存"):
                    # 開始日時の文字列化
                    if use_start_time:
                        final_start_str = datetime.datetime.combine(e_sd, e_st).strftime("%Y/%m/%d %H:%M")
                    else:
                        final_start_str = e_sd.strftime("%Y/%m/%d")

                    # 完了日時の文字列化
                    if use_end_time:
                        final_end_str = datetime.datetime.combine(e_ed, e_et).strftime("%Y/%m/%d %H:%M")
                    else:
                        # 完了日が本日で時刻チェックがない場合は空欄とみなす（運用に合わせる）
                        final_end_str = "" if not end_dt and not use_end_time else e_ed.strftime("%Y/%m/%d")
                    
                    updated = [e_occ_date.strftime("%Y/%m/%d"), e_type, e_status, e_title, e_content, e_loc, e_dept, e_req, e_staff, final_start_str, final_end_str, e_memo]
                    ws_main.update(range_name=f"A{row_idx}:L{row_idx}", values=[updated])
                    st.success("スプレッドシートを更新しました！")
                    st.rerun()
        else:
            st.warning("編集したいタスクを上の表から選択してください。")
