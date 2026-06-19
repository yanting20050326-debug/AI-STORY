import os
import streamlit as st
import streamlit.components.v1 as components
import io
import datetime
import base64
import requests
import random
import urllib.parse
from PIL import Image
from gtts import gTTS

# ─────────────────────────────────────────────
# API 設定
# ─────────────────────────────────────────────
ENV_GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile" 

# ─────────────────────────────────────────────
# 基本設定 & 強化深色主題 CSS
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI 動態繪本生成器",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="auto", 
)

st.markdown("""
<style>
    /* 強制全面深色模式 */
    :root {
        --primary: #B39DDB;
        --accent:  #FFD54F;
        --bg-main: #121212;
        --bg-card: #1E1E2E;
        --text:    #E0E0E0;
    }
    
    .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] {
        background-color: #181818 !important;
        border-right: 1px solid #2A2A3A;
    }
    h1, h2, h3, h4, h5, p, span, div, label { 
        color: var(--text) !important; 
    }
    h1, h2, h3 { color: var(--primary) !important; }
    
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #2A2A3A !important;
        color: white !important;
    }

    .story-card {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        margin-bottom: 20px;
        line-height: 1.9;
        font-size: 1.1rem;
        border: 1px solid #2A2A3A;
    }
    .badge {
        display: inline-block;
        background: #312B47;
        color: var(--primary) !important;
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 2px 3px;
        border: 1px solid var(--primary);
    }
    
    /* Slogan 動態文字特效 (拆分內外層) */
    .slogan-float {
        animation: floatUpDown 3s ease-in-out infinite;
        display: inline-block;
        margin-bottom: 1.5rem;
    }
    .slogan-shine {
        font-size: 1.35rem;
        font-weight: 700;
        background: linear-gradient(270deg, #FFD54F, #B39DDB, #FFD54F);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        color: transparent;
        animation: shineBg 3s linear infinite;
    }
    @keyframes floatUpDown {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-6px); }
    }
    @keyframes shineBg {
        to { background-position: 200% center; }
    }
    
    /* 隨機魔法貼圖動態特效 */
    .sticker-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 180px;
        margin-top: 20px;
        position: relative;
    }
    .magic-sticker {
        font-size: 80px;
        animation: float-book 4s ease-in-out infinite;
        filter: drop-shadow(0 0 25px rgba(179, 157, 219, 0.7));
        z-index: 2;
    }
    .sparkle {
        position: absolute;
        animation: twinkle 2s ease-in-out infinite;
    }
    .sp-1 { top: 15px; left: 25%; font-size: 24px; animation-delay: 0s; }
    .sp-2 { top: 45px; right: 25%; font-size: 32px; animation-delay: 0.5s; }
    .sp-3 { bottom: 35px; left: 30%; font-size: 20px; animation-delay: 1.2s; }
    .sp-4 { bottom: 50px; right: 35%; font-size: 26px; animation-delay: 1.8s; }
    
    @keyframes float-book {
        0% { transform: translateY(0px) rotate(-3deg); }
        50% { transform: translateY(-18px) rotate(4deg); }
        100% { transform: translateY(0px) rotate(-3deg); }
    }
    @keyframes twinkle {
        0%, 100% { opacity: 0.2; transform: scale(0.7) rotate(0deg); filter: drop-shadow(0 0 5px #FFD54F); }
        50% { opacity: 1; transform: scale(1.3) rotate(20deg); filter: drop-shadow(0 0 15px #FFD54F); }
    }
    
    /* 動態運鏡特效 */
    .ken-burns-container {
        overflow: hidden;
        border-radius: 16px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.6);
        border: 1px solid #2A2A3A;
    }
    .ken-burns-img {
        width: 100%;
        display: block;
        transform-origin: center;
        animation: panZoom 18s ease-in-out infinite alternate;
    }
    @keyframes panZoom {
        0% { transform: scale(1) translate(0, 0); }
        100% { transform: scale(1.15) translate(-2%, 3%); }
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Session State 初始化
# ─────────────────────────────────────────────
defaults = {
    "story_text": "",
    "story_paragraphs": [],
    "image_bytes": [],
    "audio_bytes": None,
    "history": [],          
    "current_meta": {},
    "page": "generator",    
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# 側邊欄
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("📖 動態繪本")
    st.markdown("---")

    nav = st.radio(
        "導覽",
        ["✨ 故事生成器", "👨‍👩‍👧 家長儀表板"],
        index=0 if st.session_state.page == "generator" else 1,
        label_visibility="collapsed",
    )
    st.session_state.page = "generator" if nav == "✨ 故事生成器" else "dashboard"

    st.markdown("---")
    st.subheader("📚 視覺設定")
    difficulty = st.selectbox("閱讀年齡層", ["3-4 歲 (幼童)", "5-6 歲 (大班)", "7-8 歲 (初小)"])
    generate_images = st.toggle("🎨 生成故事插圖", value=True)
    num_illustrations = st.selectbox("插圖數量", [1, 2, 3, 4], index=3)
    
    st.markdown("---")
    st.subheader("🔊 語音設定")
    auto_audio = st.toggle("自動生成語音朗讀", value=True)
    audio_speed = st.selectbox("朗讀語速", [1.0, 1.25, 1.5], index=0)

# ─────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────
def generate_story_with_groq(prompt: str, max_tokens: int = 1024) -> str:
    headers = {"Authorization": f"Bearer {ENV_GROQ_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "max_tokens": max_tokens}
    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API 錯誤（{resp.status_code}）")
    return resp.json()["choices"][0]["message"]["content"].strip()

def generate_image_with_pollinations(english_action: str, style: str) -> bytes | None:
    prompt = (
        f"A children's picture book illustration in {style} style. "
        f"{english_action}. "
        f"Bright friendly colors, highly detailed, child-safe, no text, storybook aesthetic."
    )
    encoded_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999) 
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model=flux&width=1024&height=768&seed={seed}&nologo=true"
    
    try:
        resp = requests.get(image_url, timeout=60)
        if resp.status_code == 200: return resp.content
    except: pass
    return None

def generate_audio(text: str) -> bytes:
    tts = gTTS(text=text, lang='zh-tw', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()

def create_html_story(character: str, story_paragraphs: list, image_bytes_list: list) -> bytes:
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{character} 的專屬繪本</title>
        <style>
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, 'Microsoft JhengHei', sans-serif;
                background-color: #121212;
                color: #E0E0E0;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1 {{ color: #B39DDB; text-align: center; margin-bottom: 40px; font-size: 2.5em; }}
            .page {{ margin-bottom: 50px; text-align: center; }}
            img {{
                max-width: 100%;
                border-radius: 16px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.8);
                margin-bottom: 20px;
            }}
            p {{
                font-size: 1.3rem;
                line-height: 1.9;
                text-align: left;
                padding: 25px;
                background: #1E1E2E;
                border-radius: 16px;
                border: 1px solid #2A2A3A;
            }}
        </style>
    </head>
    <body>
        <h1>📖 {character} 的專屬繪本</h1>
    """
    
    img_idx = 0
    img_spacing = max(1, len(story_paragraphs) // max(1, len(image_bytes_list))) if image_bytes_list else 1

    for i, para in enumerate(story_paragraphs):
        html += "<div class='page'>"
        if image_bytes_list and img_idx < len(image_bytes_list) and i % img_spacing == 0:
            img_b64 = base64.b64encode(image_bytes_list[img_idx]).decode()
            html += f"<img src='data:image/png;base64,{img_b64}'>"
            img_idx += 1
        html += f"<p>{para}</p></div>"

    while img_idx < len(image_bytes_list):
        img_b64 = base64.b64encode(image_bytes_list[img_idx]).decode()
        html += f"<div class='page'><img src='data:image/png;base64,{img_b64}'></div>"
        img_idx += 1

    html += "</body></html>"
    return html.encode('utf-8')

# ─────────────────────────────────────────────
# 頁面：故事生成器
# ─────────────────────────────────────────────
if st.session_state.page == "generator":

    st.title("📖 AI 動態繪本生成器")
    
    st.markdown("""
        <div class="slogan-float">
            <span class="slogan-shine">✨ 無須註冊，無次數限制，快樂學習 ✨</span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    if not ENV_GROQ_KEY:
        st.error("⚠️ 系統尚未偵測到 GROQ_API_KEY 環境變數，請確認伺服器設定。")
        st.stop()

    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        st.subheader("🎭 故事設定")
        character = st.text_input("主角叫什麼名字？", placeholder="例如：小紅帽、大野狼、小鱷魚…")
        scene = st.text_input("故事在哪裡發生？", placeholder="例如：魔法森林、海底世界…")
        
        theme_options = ["友情", "勇氣", "冒險", "親情", "分享", "探索", "自訂..."]
        selected_theme = st.selectbox("今天想聽什麼主題？", theme_options)
        
        if selected_theme == "自訂...":
            theme = st.text_input("✏️ 請輸入你想自訂的主題：", placeholder="例如：萬聖節派對、認識恐龍...")
        else:
            theme = selected_theme
            
        generate_btn = st.button("✨ 開始生成專屬繪本", use_container_width=True, type="primary")

    with col_r:
        st.subheader("💡 使用提示")
        st.info("輸入主角、場景與主題後，點擊生成，故事與動態插圖將同步呈現！生成完畢後可以將獨一無二的繪本下載珍藏。")
        
        # 🌟 隨機盲盒貼圖邏輯
        stickers = ["📖", "🚀", "🪄", "🔮", "🦄", "👑", "🧸", "🎨", "🧩"]
        random_sticker = random.choice(stickers)
        
        st.markdown(f"""
        <div class="sticker-container">
            <div class="sparkle sp-1">✨</div>
            <div class="sparkle sp-2">🌟</div>
            <div class="sparkle sp-3">✨</div>
            <div class="sparkle sp-4">💫</div>
            <div class="magic-sticker">{random_sticker}</div>
        </div>
        """, unsafe_allow_html=True)

    if generate_btn:
        if not character or not scene or not theme: 
            st.warning("請完整填寫主角、場景與主題！")
        else:
            with st.spinner("🔮 AI 正在為您創作故事與分鏡…"):
                try:
                    story_prompt = f"你是一位專為兒童寫作的繪本作家。請為「{difficulty}」的孩子創作一篇關於「{theme}」的故事。主角是「{character}」，故事發生在「{scene}」。請用生動有趣、符合該年齡層的詞彙，長度約 400 到 600 字。分成 4 到 6 個段落，不要加標題或編號。"
                    story_text = generate_story_with_groq(story_prompt)
                    st.session_state.story_text = story_text
                    st.session_state.story_paragraphs = [p.strip() for p in story_text.split("\n\n") if p.strip()]
                    st.session_state.audio_bytes = None
                    
                    record = {
                        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "character": character, "scene": scene, "theme": theme, 
                        "difficulty": difficulty, "text": story_text,
                    }
                    st.session_state.history.append(record)
                    st.session_state.current_meta = record

                except Exception as e:
                    st.error(f"故事生成失敗：{e}")
                    st.stop()

            st.session_state.image_bytes = []
            if generate_images:
                paragraphs = st.session_state.story_paragraphs
                scenes_to_illustrate = []
                
                if paragraphs:
                    for i in range(num_illustrations):
                        idx = int(i * len(paragraphs) / num_illustrations)
                        idx = min(idx, len(paragraphs) - 1)
                        scenes_to_illustrate.append(paragraphs[idx])

                prog = st.progress(0, text="🎨 正在規劃插圖分鏡…")
                styles = ["soft watercolor", "colored pencil", "pastel drawing", "paper cut-out art", "oil painting", "3D Pixar animation"]
                book_style = random.choice(styles)
                
                for idx, scene_paragraph in enumerate(scenes_to_illustrate):
                    prog.progress((idx) / len(scenes_to_illustrate), text=f"🎨 正在繪製插圖 {idx+1}/{len(scenes_to_illustrate)}...")
                    
                    translation_prompt = (
                        f"Convert the main action of the following Chinese story paragraph into an English image generation prompt (max 30 words). "
                        f"CRITICAL RULE: The main character is '{character}'. If the character is an animal, object, or fantasy creature, you MUST explicitly state this species for EVERY related character in the scene (e.g., explicitly write 'a mother crocodile' instead of just 'a mother', 'brother bear' instead of 'brother'). Do NOT generate human characters unless explicitly requested. "
                        f"Setting: '{scene}'. "
                        f"Paragraph: {scene_paragraph}\n\n"
                        f"Output ONLY the English prompt."
                    )
                    try:
                        english_action = generate_story_with_groq(translation_prompt, max_tokens=60)
                    except:
                        english_action = f"The character {character} in {scene}"
                    
                    img_data = generate_image_with_pollinations(english_action, book_style)
                    if img_data: 
                        st.session_state.image_bytes.append(img_data)
                        
                prog.empty()

            if auto_audio:
                with st.spinner("🎙️ 正在錄製 AI 語音導讀…"):
                    try:
                        st.session_state.audio_bytes = generate_audio(st.session_state.story_text)
                    except Exception as e:
                        st.error(f"語音生成失敗：{e}")

    if st.session_state.story_text:
        st.markdown("---")
        st.subheader("📚 你的專屬繪本")

        if st.session_state.audio_bytes:
            st.success(f"🎵 語音導讀已為您準備好！(語速：{audio_speed}x)")
            b64_audio = base64.b64encode(st.session_state.audio_bytes).decode()
            audio_html = f"""
                <audio id="storyAudio" controls autoplay style="width: 100%; height: 50px; border-radius: 8px; outline: none;">
                    <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
                </audio>
                <script>
                    var audio = document.getElementById("storyAudio");
                    audio.playbackRate = {audio_speed};
                </script>
            """
            components.html(audio_html, height=70)

        meta = st.session_state.current_meta
        if meta:
            st.markdown(
                f'<span class="badge">👤 {meta.get("character","")}</span>'
                f'<span class="badge">🌍 {meta.get("scene","")}</span>'
                f'<span class="badge">💡 {meta.get("theme","")}</span>',
                unsafe_allow_html=True,
            )
        st.markdown("")

        paragraphs = st.session_state.story_paragraphs
        image_bytes_list = st.session_state.image_bytes
        img_idx = 0

        img_spacing = max(1, len(paragraphs) // max(1, len(image_bytes_list))) if image_bytes_list else 1

        for i, para in enumerate(paragraphs):
            if image_bytes_list and img_idx < len(image_bytes_list) and i % img_spacing == 0:
                img_b64 = base64.b64encode(image_bytes_list[img_idx]).decode()
                st.markdown(
                    f'<div class="ken-burns-container"><img src="data:image/png;base64,{img_b64}" class="ken-burns-img"></div>', 
                    unsafe_allow_html=True
                )
                img_idx += 1
            st.markdown(f'<div class="story-card">{para}</div>', unsafe_allow_html=True)

        while img_idx < len(image_bytes_list):
            img_b64 = base64.b64encode(image_bytes_list[img_idx]).decode()
            st.markdown(
                f'<div class="ken-burns-container"><img src="data:image/png;base64,{img_b64}" class="ken-burns-img"></div>', 
                unsafe_allow_html=True
            )
            img_idx += 1

        st.markdown("---")

        c1, c2 = st.columns(2)
        with c1:
            html_content = create_html_story(meta.get("character", "故事"), st.session_state.story_paragraphs, st.session_state.image_bytes)
            st.download_button(
                label="📥 下載專屬繪本 (HTML檔)", 
                data=html_content, 
                file_name=f"{meta.get('character','story')}_繪本.html", 
                mime="text/html", 
                use_container_width=True
            )
        with c2:
            if st.button("🔄 重新生成", use_container_width=True):
                st.session_state.story_text = ""
                st.session_state.story_paragraphs = []
                st.session_state.image_bytes = []
                st.session_state.audio_bytes = None
                st.rerun()

# ─────────────────────────────────────────────
# 頁面：家長儀表板
# ─────────────────────────────────────────────
elif st.session_state.page == "dashboard":

    st.title("👨‍👩‍👧 家長儀表板")
    st.markdown("追蹤孩子的閱讀歷程，了解學習成長。")
    st.markdown("---")

    history = st.session_state.history

    if not history:
        st.info("還沒有閱讀紀錄！請先到「故事生成器」生成幾篇故事。")
        st.stop()

    total = len(history)
    themes_used = len({h["theme"] for h in history})
    chars_used = len({h["character"] for h in history})
    latest_date = history[-1]["date"] if history else "—"

    c1, c2, c3, c4 = st.columns(4)
    for col, num, label in zip(
        [c1, c2, c3, c4],
        [total, themes_used, chars_used, latest_date],
        ["📚 總故事篇數", "💡 主題種類", "👤 不同主角", "🕐 最近閱讀"],
    ):
        col.markdown(
            f'<div class="metric-box">'
            f'<div class="metric-num">{num}</div>'
            f'<div class="metric-label">{label}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("📋 閱讀紀錄")

    for i, item in enumerate(reversed(history)):
        with st.expander(f"📖 {item['character']} 在「{item['scene']}」的故事  ｜  {item['theme']}  ｜  {item['date']}"):
            st.markdown(
                f'<span class="badge">📅 {item["date"]}</span>'
                f'<span class="badge">💡 {item["theme"]}</span>'
                f'<span class="badge">🎓 {item["difficulty"]}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown(f'<div class="story-card">{item["text"]}</div>', unsafe_allow_html=True)

    st.markdown("---")
    
    if st.button("🗑️ 清除所有閱讀紀錄", type="secondary"):
        st.session_state.history = []
        st.session_state.story_text = ""
        st.session_state.story_paragraphs = []
        st.session_state.image_bytes = []
        st.success("已清除所有紀錄。")
        st.rerun()
