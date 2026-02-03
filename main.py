import streamlit as st
import gspread
import pandas as pd
import datetime
import requests
import json
from google.oauth2.credentials import Credentials

# --- ページ設定 ---
st.set_page_config(page_title="総務部タスク管理システム", layout="wide")

# --- 認証とスプレッドシートの取得（サーバー専用版） ---
@st.cache_resource
def get_ss_connection():
    # StreamlitのSecretsからJSON文字列を辞書として読み込む
    authorized_user_info = json.loads(st.secrets["gcp_authorized_user"])
    
    # サーバー上でログイン画面を出さずに認証を通す設定
    creds = Credentials.from_authorized_user_info(authorized_user_info)
    gc = gspread.authorize(creds)
    
    # ★重要：ここに自分のGoogleスプレッドシートのURLを貼り付けてください
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1bRXFLHiSsYVpofyXSf2UUcAsO_gM37aHsUv0CogmfPI/edit?gid=0#gid=0"
    
    return gc.open_by_url(SPREADSHEET_URL)

# --- Google Chat通知設定 ---
# (以前と同じURLを使用します)
CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAAAD-bZDK4/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=gK0I12cncnoO_AzBlSfLtoOrIH1v-mKINo1Iah0OTbw" 

def send_chat_notification(message):
    try:
        payload = {"text": message}
        requests.post(CHAT_WEBHOOK_URL, json=payload)
    except Exception as e:
        st.error(f"通知の送信に失敗しました: {e}")

# --- アプリのメイン処理 ---
def main():
    st.title("🏢 総務部 業務管理システム")
    
    try:
        sh = get_ss_connection()
        ws = sh.get_worksheet(0)
    except Exception as e:
        st.error(f"スプレッドシートへの接続に失敗しました。Secretsの設定を確認してください。: {e}")
        return

    # データの読み込み
    data = ws.get_all_records()
    df = pd.DataFrame(data)

    # タブの作成
    tab1, tab2 = st.tabs(["📋 タスク一覧・更新", "➕ 新規タスク登録"])

    with tab1:
        st.subheader("現在のタスク")
        if not df.empty:
            # 担当者などで絞り込み（オプション）
            filter_user = st.selectbox("担当者でフィルター", ["全員"] + list(df["担当者"].unique()))
            display_df = df if filter_user == "全員" else df[df["担当者"] == filter_user]
            
            # テーブル表示
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("現在登録されているタスクはありません。")

    with tab2:
        st.subheader("新規タスクの登録")
        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_task = st.text_input("タスク名")
                new_user = st.selectbox("担当者", ["担当A", "担当B", "担当C"]) # 必要に応じて変更
            with col2:
                new_date = st.date_input("期限", datetime.date.today())
                new_status = st.selectbox("ステータス", ["未着手", "進行中", "完了"])
            
            submit = st.form_submit_button("登録する")
            
            if submit:
                if new_task:
                    new_row = [new_task, new_user, str(new_date), new_status]
                    ws.append_row(new_row)
                    st.success("タスクを登録しました！")
                    
                    # Google Chatへ通知
                    msg = f"🔔 *新しいタスクが登録されました*\n内容: {new_task}\n担当: {new_user}\n期限: {new_date}"
                    send_chat_notification(msg)
                    st.rerun()
                else:
                    st.warning("タスク名を入力してください。")

if __name__ == "__main__":
    main()
