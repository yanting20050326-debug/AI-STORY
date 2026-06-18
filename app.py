import os
import streamlit as st
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
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
# 基本設定 & 深色主題 CSS
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI 動態繪本生成器",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    :root {
        --primary: #B39DDB;
        --accent:  #FFD54F;
        --bg-main: #121212;
        --bg-card: #1E1E2E;
        --text:    #E0E0E0;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: var(--bg-main) !important;
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] {
        background: #181818 !important;
    }
    h1, h2, h3, h4 { color: var(--primary) !important; }
    p, span, div { color: var(--text) !important; }
    
    .story-card {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        margin-bottom: 20px;
        line-height: 1.9;
        font-size: 1.08rem;
        color: var(--text);
        border: 1px solid #2A2A3A;
    }
    .badge {
        display: inline-block;
        background: #312B47;
        color: var(--primary);
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 2px 3px;
        border: 1px solid var(--primary);
    }
    .metric-box {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        border: 1px solid #2A2A3A;
    }
    .metric-num { font-size: 2.2rem; font-weight: 700; color: var(--accent); }
    .metric-label { font-size: 0.85rem; color: #A0A0A0; }
    
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
    st.subheader("📚 閱讀設定")
    difficulty = st.selectbox("閱讀年齡層", ["3-4 歲 (幼童)", "5-6 歲 (大班)", "7-8 歲 (初小)"])
    generate_images = st.toggle("🎨 生成故事插圖", value=True)
    num_illustrations = st.slider("插圖數量", 1, 4, 4)
    auto_audio = st.toggle("🔊 自動生成語音朗讀", value=True)

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
    tts = gTTS(text=text, lang='zh-tw')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()

# ⚠️ 更新為支援舊版 FPDF 的 TTF 字體來源
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/notosanstc/NotoSansTC-Regular.ttf"
FONT_PATH = "NotoSansTC-Regular.ttf"
FONT_NAME = "NotoSansTC"

@st.cache_resource
def download_font():
    if not os.path.exists(FONT_PATH):
        try:
            with open(FONT_PATH, "wb") as f:
                f.write(requests.get(FONT_URL, timeout=30).content)
        except: pass
download_font()

def create_story_pdf(text: str, character: str, image_bytes_list: list) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    try:
        # 強制指定 uni=True 以支援 UTF-8 中文字元
        pdf.add_font(FONT_NAME, "", FONT_PATH, uni=True)
        use_font = FONT_NAME
    except: 
        use_font = "Arial"
    
    pdf.set_font(use_font, size=22)
    # 如果字體載入失敗退回 Arial，為了防止崩潰，移除標題的中文字
    safe_title = f"{character} 的專屬故事" if use_font != "Arial" else "Storybook"
    pdf.cell(0, 16, safe_title, ln=True, align="C")
    
    if image_bytes_list:
        try:
            # 寫入暫存圖片供 PDF 讀取
            img_path = "temp_pdf_image.png"
            with open(img_path, "wb") as f: f.write(image_bytes_list[0])
            pdf.image(img_path, x=30, w=150)
            pdf.ln(4)
        except: pass
        
    pdf.set_font(use_font, size=12)
    safe_text = text if use_font != "Arial" else "Font error: Could not load Chinese font. Please try again."
    pdf.multi_cell(0, 8, safe_text)
    return bytes(pdf.output())

# ─────────────────────────────────────────────
# 頁面：故事生成器
# ─────────────────────────────────────────────
if st.session_state.page == "generator":

    st.title("📖 AI 動態繪本生成器")
    st.markdown("##### 結合視覺特效與語音，打造沉浸式閱讀體驗。")
    st.markdown("---")

    if not ENV_GROQ_KEY:
        st.error("⚠️ 系統尚未偵測到 GROQ_API_KEY 環境變數，請確認伺服器設定。")
        st.stop()

    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        st.subheader("🎭 故事設定")
        character = st.text_input("主角叫什麼名字？", placeholder="例如：小紅帽、大野狼…")
        scene = st.text_input("故事在哪裡發生？", placeholder="例如：魔法森林、海底世界…")
        theme = st.selectbox("今天想聽什麼主題？", ["友情", "勇氣", "冒險", "親情", "分享", "探索"])
        generate_btn = st.button("✨ 開始生成專屬繪本", use_container_width=True, type="primary")

    with col_r:
        st.subheader("💡 使用提示")
        st.info("輸入主角、場景與主題後，點擊生成，故事與動態插圖將同步呈現！")

    if generate_btn:
        if not character or not scene: 
            st.warning("請填寫主角與場景！")
        else:
            with st.spinner("🔮 AI 正在為您創作故事與分鏡…"):
                try:
                    # 1. 生成主線故事
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

            # 2. 處理圖片與分鏡
            st.session_state.image_bytes = []
            if generate_images:
                paragraphs = st.session_state.story_paragraphs
                scenes_to_illustrate = []
                
                # 確保精準選出使用者指定的圖片數量 (1~4 張)
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
                        f"Extract the main visual action from the following Chinese story paragraph and describe it in a concise English image prompt (maximum 20 words). "
                        f"The main character is '{character}'. The setting is '{scene}'. "
                        f"Paragraph: {scene_paragraph}\n\nOutput ONLY the English description."
                    )
                    try:
                        english_action = generate_story_with_groq(translation_prompt, max_tokens=50)
                    except:
                        english_action = f"The character {character} in {scene}"
                    
                    img_data = generate_image_with_pollinations(english_action, book_style)
                    if img_data: 
                        st.session_state.image_bytes.append(img_data)
                        
                prog.empty()

            # 3. 全自動生成語音 (如果開關有打開)
            if auto_audio:
                with st.spinner("🎙️ 正在錄製 AI 語音導讀…"):
                    try:
                        st.session_state.audio_bytes = generate_audio(st.session_state.story_text)
                    except Exception as e:
                        st.error(f"語音生成失敗：{e}")

    if st.session_state.story_text:
        st.markdown("---")
        st.subheader("📚 你的專屬繪本")

        # 顯示語音播放器
        if st.session_state.audio_bytes:
            st.success("🎵 語音導讀已為您準備好！")
            st.audio(st.session_state.audio_bytes, format="audio/mp3", autoplay=True)

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

        # 將生成的圖片均勻分配到段落中顯示
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

        # 把剩餘圖片貼到最後面
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
            story_pdf = create_story_pdf(st.session_state.story_text, meta.get("character", "故事"), st.session_state.image_bytes)
            st.download_button("🖨️ 匯出故事 PDF", data=story_pdf, file_name=f"{meta.get('character','story')}_繪本.pdf", mime="application/pdf", use_container_width=True)
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
    report_pdf = create_story_pdf("這是一份歷史紀錄總覽 (開發中)", "閱讀報告", [])
    st.download_button(
        "⬇️ 下載 PDF 學習報告",
        data=report_pdf,
        file_name=f"閱讀報告_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
    )

    if st.button("🗑️ 清除所有閱讀紀錄", type="secondary"):
        st.session_state.history = []
        st.session_state.story_text = ""
        st.session_state.story_paragraphs = []
        st.session_state.image_bytes = []
        st.success("已清除所有紀錄。")
        st.rerun()
