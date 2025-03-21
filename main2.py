import streamlit as st
from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
import openai
import time

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数からAPIキーを取得
API_KEY = os.getenv('DEVELOPER_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# YouTube APIクライアントの作成
youtube = build("youtube", "v3", developerKey=API_KEY)

# OpenAI APIキーを設定
openai.api_key = OPENAI_API_KEY

def search_youtube(keyword, max_results=50):
    """指定したキーワードでYouTube検索を行い、タイトル・URL・再生回数・いいね数を取得"""
    search_response = youtube.search().list(
        q=keyword,
        part="snippet",
        type="video",
        maxResults=max_results
    ).execute()

    video_data = []

    for item in search_response["items"]:
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        url = f"https://www.youtube.com/watch?v={video_id}"

        # 動画の詳細情報を取得（再生回数、いいね数など）
        video_response = youtube.videos().list(
            part="statistics",
            id=video_id
        ).execute()

        if "items" in video_response and len(video_response["items"]) > 0:
            statistics = video_response["items"][0]["statistics"]
            view_count = statistics.get("viewCount", "N/A")
            like_count = statistics.get("likeCount", "N/A")
        else:
            view_count = "N/A"
            like_count = "N/A"

        video_data.append({
            "title": title,
            "url": url,
            "views": view_count,
            "likes": like_count
        })

    return video_data

def generate_video_title_and_plan(theme, client_name, videos):
    video_descriptions = "\n".join([f"Title: {video['title']}, URL: {video['url']}, Views: {video['views']}, Likes: {video['likes']}" for video in videos])
    prompt_template = (
        "あなたは動画制作のディレクターです。以下の動画情報に基づいて、テーマ「{theme}」に沿った新しい動画のタイトルと企画構成を作成してください。\n\n"
        "クライアント名: {client_name}\n\n"
        "{video_descriptions}\n\n"
        "新しい動画のタイトルと企画構成:\n"
        "1. タイトル\n"
        "2. 企画構成\n"
        "   - ペルソナ\n"
        "   - その動画は視聴したターゲットにどう感じ、どのような行動を起こさせるものか\n"
        "   - マーケティング視点での企画内容の説明\n"
        "   - CTA\n"
        "   - ざっくりとした構成案3個\n"
    )
    prompt = prompt_template.format(theme=theme, client_name=client_name, video_descriptions=video_descriptions)
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000
    )
    
    return response.choices[0].message['content'].strip()

def generate_storyboard(plan):
    prompt_template = (
        "以下の動画企画構成に基づいて、60秒の動画の絵コンテを作成してください。各シーンの秒数を指定し、表形式で出力してください。\n\n"
        "{plan}\n\n"
        "絵コンテ:\n"
        "| シーン番号 | タイムコード | シーンの内容 | 伝えたいメッセージ |\n"
        "|-------------|--------------|--------------|--------------------|\n"
    )
    prompt = prompt_template.format(plan=plan)
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000
    )
    
    storyboard_text = response.choices[0].message['content'].strip()
    
    # 各シーンの画像を生成
    scenes = storyboard_text.split("\n")[4:]  # ヘッダー行をスキップ
    images = []
    for scene in scenes:
        if scene.strip():
            scene_parts = scene.split("|")
            if len(scene_parts) > 3:
                scene_description = scene_parts[3].strip()
                try:
                    image_response = openai.Image.create(
                        prompt=scene_description,
                        n=1,
                        size="256x256"
                    )
                    image_url = image_response['data'][0]['url']
                    images.append((scene, image_url))
                    time.sleep(12)  # レート制限を回避するために遅延を追加
                except openai.error.RateLimitError:
                    st.warning("レート制限を超えました。少し待ってから再試行してください。")
                    break
    
    return storyboard_text, images

# Streamlitアプリの設定
st.title("動画企画構成制作マシーン")

# キーワード入力フィールド
keyword = st.text_input("検索キーワードを入力してください", key="keyword_input")
theme = st.text_input("テーマを入力してください", key="theme_input")
client_name = st.text_input("クライアント名を入力してください", key="client_name_input")

# YouTube検索
if st.button("検索", key="search_button"):
    with st.spinner("検索中..."):
        results = search_youtube(keyword)
    st.success("検索完了")

    # 動画タイトルと企画構成生成
    if results:
        with st.spinner("動画タイトルと企画構成生成中..."):
            video_title_and_plan = generate_video_title_and_plan(theme, client_name, results)
        st.success("新しい動画のタイトルと企画構成:")
        st.write(video_title_and_plan)
        
        # 構成案の選択
        plan_options = ["構成案1", "構成案2", "構成案3"]
        if "selected_plan" not in st.session_state:
            st.session_state.selected_plan = plan_options[0]
        selected_plan = st.radio("構成案を選択してください:", plan_options, key="plan_radio", index=plan_options.index(st.session_state.selected_plan))
        
        # 選択された構成案をセッションステートに保存
        st.session_state.selected_plan = selected_plan

