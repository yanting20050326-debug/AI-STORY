import os
import streamlit as st
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
import io
import json
import datetime
import base64
import requests
from PIL import Image
from gtts import gTTS  # 新增：語音朗讀套件

# ─────────────────────────────────────────────
# 從環境變數讀取 API Key（Render 環境變數設定）
# ─────────────────────────────────────────────
ENV_GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
ENV_HF_KEY = os.environ.get("HUGGINGFACE_API_KEY", "")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile" 

POLLINATIONS_API = "https://image.pollinations.ai/prompt/"

# ─────────────────────────────────────────────
# 基本設定 & CSS 美化
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
        --primary: #7C5CBF;
        --accent:  #F9A825;
        --bg-card: #FDFAF6;
        --text:    #2E2E3A;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f5f0ff 0%, #fff8e7 100%);
    }
    h1 { color: var(--primary) !important; }
    h2, h3 { color: #4a3f6b !important; }
    
    .story-card {
        background: var(--bg-card);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(124,92,191,0.10);
        margin-bottom: 20px;
        line-height: 1.9;
        font-size: 1.08rem;
        color: var(--text);
    }
    .badge {
        display: inline-block;
        background: #ede7ff;
        color: var(--primary);
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 2px 3px;
    }
    .metric-box {
        background: white;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    }
    .metric-num { font-size: 2.2rem; font-weight: 700; color: var(--primary); }
    .metric-label { font-size: 0.85rem; color: #888; }
    
    /* 動態運鏡特效 (Ken Burns Effect) */
    .ken-burns-container {
        overflow: hidden;
        border-radius: 16px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(124,92,191,0.15);
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
    "audio_bytes": None,    # 新增：儲存語音資料
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
    st.image("https://i.imgur.com/placeholder.png", width=60)
    st.title("📖 動態繪本生成器")
    st.markdown("---")

    nav = st.radio(
        "導覽",
        ["✨ 故事生成器", "👨‍👩‍👧 家長儀表板"],
        index=0 if st.session_state.page == "generator" else 1,
        label_visibility="collapsed",
    )
    st.session_state.page = "generator" if nav == "✨ 故事生成器" else "dashboard"

    st.markdown("---")
    st.subheader("⚙️ API 設定")
    groq_key = ENV_GROQ_KEY if ENV_GROQ_KEY else st.text_input("Groq API Key", type="password")
    hf_key = ENV_HF_KEY if ENV_HF_KEY else st.text_input("Hugging Face Token", type="password")
    if ENV_GROQ_KEY: st.success("✅ Groq Key 已設定")
    if ENV_HF_KEY: st.success("✅ Hugging Face Key 已設定")

    st.markdown("---")
    st.subheader("📚 閱讀設定")
    difficulty = st.selectbox("閱讀年齡層", ["3-4 歲 (幼童)", "5-6 歲 (大班)", "7-8 歲 (初小)"])
    generate_images = st.toggle("🎨 生成故事插圖", value=True)
    num_illustrations = st.slider("插圖數量", 1, 4, 2)

# ─────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────
def split_into_paragraphs(text: str, n: int) -> list[str]:
    sentences = [s.strip() for s in text.replace("。", "。\n").split("\n") if s.strip()]
    if not sentences: return [text]
    chunk_size = max(1, len(sentences) // n)
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        chunk = "".join(sentences[i : i + chunk_size])
        if chunk: chunks.append(chunk)
    return chunks[:n]

def generate_story_with_groq(groq_key: str, prompt: str) -> str:
    headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.9, "max_tokens": 1024}
    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API 錯誤（{resp.status_code}）")
    return resp.json()["choices"][0]["message"]["content"].strip()

def generate_image_with_pollinations(scene_desc: str, character: str, scene: str) -> bytes | None:
    prompt = (
        f"A charming children's picture book illustration in a soft watercolor style. "
        f"Scene: {scene_desc[:200]}. "
        f"The main character is '{character}' set in '{scene}'. "
        f"Bright friendly colors, no text, child-safe, storybook aesthetic."
    )
    try:
        resp = requests.get(f"{POLLINATIONS_API}{prompt}", timeout=60)
        if resp.status_code == 200: return resp.content
    except: pass
    return None

def generate_audio(text: str) -> bytes:
    """使用 gTTS 將文字轉換為語音位元組"""
    tts = gTTS(text=text, lang='zh-tw')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp.read()

# 字體下載與 PDF 報表功能 (保持不變)
FONT_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
FONT_PATH = "NotoSansCJKtc-Regular.otf"
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
        pdf.add_font(FONT_NAME, "", FONT_PATH, uni=True)
        use_font = FONT_NAME
    except: use_font = "Arial"
    
    pdf.set_font(use_font, size=22)
    pdf.cell(0, 16, f"{character} 的專屬故事", ln=True, align="C")
    if image_bytes_list:
        try:
            with open("/tmp/story_img_0.png", "wb") as f: f.write(image_bytes_list[0])
            pdf.image("/tmp/story_img_0.png", x=30, w=150)
            pdf.ln(4)
        except: pass
    pdf.set_font(use_font, size=12)
    pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())

# ─────────────────────────────────────────────
# 頁面：故事生成器
# ─────────────────────────────────────────────
if st.session_state.page == "generator":

    st.title("📖 AI 動態繪本生成器")
    st.markdown("##### 結合視覺特效與語音，打造沉浸式閱讀體驗。")
    st.markdown("---")

    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        st.subheader("🎭 故事設定")
        character = st.text_input("主角叫什麼名字？", placeholder="例如：小紅帽、大野狼…")
        scene = st.text_input("故事在哪裡發生？", placeholder="例如：魔法森林、海底世界…")
        theme = st.selectbox("今天想聽什麼主題？", ["友情", "勇氣", "冒險", "親情", "分享", "探索"])
        generate_btn = st.button("✨ 開始生成專屬繪本", use_container_width=True, type="primary")

    with col_r:
        st.subheader("💡 使用提示")
        st.info("輸入主角、場景與主題後，點擊生成，故事與動態插圖將同步呈現！支援一鍵產生語音朗讀。")

    if generate_btn:
        if not groq_key: st.error("請先輸入 Groq API Key！")
        elif not character or not scene: st.warning("請填寫主角與場景！")
        else:
            with st.spinner("🔮 AI 正在為您創作故事…"):
                try:
                    prompt = f"你是一位專為兒童寫作的繪本作家。請為「{difficulty}」的孩子創作一篇關於「{theme}」的故事。主角是「{character}」，故事發生在「{scene}」。請用生動有趣、符合該年齡層的詞彙，長度約 400 到 600 字。分成 4 個段落，不要加標題或編號。"
                    story_text = generate_story_with_groq(groq_key, prompt)
                    st.session_state.story_text = story_text
                    st.session_state.story_paragraphs = [p.strip() for p in story_text.split("\n\n") if p.strip()]
                    st.session_state.audio_bytes = None # 清除前一次的語音
                    
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
            if generate_images and hf_key:
                scenes_to_illustrate = split_into_paragraphs(st.session_state.story_text, num_illustrations)
                prog = st.progress(0, text="🎨 正在生成插圖…")
                for idx, scene_desc in enumerate(scenes_to_illustrate):
                    img_data = generate_image_with_pollinations(scene_desc, character, scene)
                    if img_data: st.session_state.image_bytes.append(img_data)
                    prog.progress((idx + 1) / len(scenes_to_illustrate), text=f"🎨 插圖 {idx+1}/{len(scenes_to_illustrate)} 完成")
                prog.empty()

    if st.session_state.story_text:
        st.markdown("---")
        st.subheader("📚 你的專屬繪本")

        # 顯示標籤
        meta = st.session_state.current_meta
        if meta:
            st.markdown(
                f'<span class="badge">👤 {meta.get("character","")}</span>'
                f'<span class="badge">🌍 {meta.get("scene","")}</span>'
                f'<span class="badge">💡 {meta.get("theme","")}</span>',
                unsafe_allow_html=True,
            )
        st.markdown("")

        # 渲染故事與動態插圖
        paragraphs = st.session_state.story_paragraphs
        image_bytes_list = st.session_state.image_bytes
        img_idx = 0

        for i, para in enumerate(paragraphs):
            if image_bytes_list and img_idx < len(image_bytes_list) and i % max(1, len(paragraphs) // len(image_bytes_list)) == 0:
                # 使用 Base64 與自訂 CSS 類別渲染動態圖片
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

        # 控制項：匯出、語音、重製
        c1, c2, c3 = st.columns(3)
        with c1:
            story_pdf = create_story_pdf(st.session_state.story_text, meta.get("character", "故事"), st.session_state.image_bytes)
            st.download_button("🖨️ 匯出故事 PDF", data=story_pdf, file_name=f"{meta.get('character','story')}_繪本.pdf", mime="application/pdf", use_container_width=True)
        with c2:
            if st.button("🔊 產生並播放語音", use_container_width=True):
                with st.spinner("🎙️ 正在產生語音，請稍候..."):
                    try:
                        st.session_state.audio_bytes = generate_audio(st.session_state.story_text)
                    except Exception as e:
                        st.error(f"語音生成失敗：{e}")
        with c3:
            if st.button("🔄 重新生成", use_container_width=True):
                st.session_state.story_text = ""
                st.session_state.story_paragraphs = []
                st.session_state.image_bytes = []
                st.session_state.audio_bytes = None
                st.rerun()

        # 顯示語音播放器
        if st.session_state.audio_bytes:
            st.success("🎵 語音已準備就緒！")
            st.audio(st.session_state.audio_bytes, format="audio/mp3", autoplay=True)

# 家長儀表板 (Dashboard) 邏輯保持原狀，為節省版面此處省略，
# 你可以保留原本 elif st.session_state.page == "dashboard": 以下的程式碼。
