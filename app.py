import os
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = ['DejaVu Sans', 'sans-serif']
import io
import json
import datetime
import base64
import requests
from PIL import Image

# ─────────────────────────────────────────────
# 從環境變數讀取 API Key（Render 環境變數設定）
# 若環境變數不存在，則留空讓使用者手動輸入
# ─────────────────────────────────────────────
ENV_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
ENV_HF_KEY     = os.environ.get("HUGGINGFACE_API_KEY", "")

# Hugging Face 免費圖片生成模型
HF_IMAGE_API = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

# ─────────────────────────────────────────────
# 基本設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI 繪本故事生成器",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自訂 CSS 美化介面
st.markdown("""
<style>
    /* 主色調 */
    :root {
        --primary: #7C5CBF;
        --accent:  #F9A825;
        --bg-card: #FDFAF6;
        --text:    #2E2E3A;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f5f0ff 0%, #fff8e7 100%);
    }
    /* 標題 */
    h1 { color: var(--primary) !important; }
    h2, h3 { color: #4a3f6b !important; }
    /* 卡片區塊 */
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
    /* 章節圖說 */
    .caption-box {
        background: #ede7ff;
        border-left: 4px solid var(--primary);
        padding: 8px 14px;
        border-radius: 0 8px 8px 0;
        margin: 10px 0 6px 0;
        font-size: 0.9rem;
        color: #4a3f6b;
    }
    /* 統計數字 */
    .metric-box {
        background: white;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    }
    .metric-num { font-size: 2.2rem; font-weight: 700; color: var(--primary); }
    .metric-label { font-size: 0.85rem; color: #888; }
    /* 徽章 */
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
    /* 歷史紀錄列 */
    .history-row {
        background: white;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-left: 4px solid var(--accent);
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Session State 初始化
# ─────────────────────────────────────────────
defaults = {
    "story_text": "",
    "story_paragraphs": [],
    "image_urls": [],
    "image_bytes": [],
    "history": [],          # [{date, character, scene, theme, difficulty, text}]
    "current_meta": {},
    "page": "generator",    # generator | dashboard
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# 側邊欄
# ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://i.imgur.com/placeholder.png", width=60)  # 可換成 logo
    st.title("📖 繪本生成器")
    st.markdown("---")

    # 頁面切換
    nav = st.radio(
        "導覽",
        ["✨ 故事生成器", "👨‍👩‍👧 家長儀表板"],
        index=0 if st.session_state.page == "generator" else 1,
        label_visibility="collapsed",
    )
    st.session_state.page = "generator" if nav == "✨ 故事生成器" else "dashboard"

    st.markdown("---")
    st.subheader("⚙️ API 設定")

    # 若環境變數已設定 Key，顯示已就緒提示，不需使用者輸入
    if ENV_GEMINI_KEY:
        st.success("✅ Gemini Key 已設定")
        gemini_key = ENV_GEMINI_KEY
    else:
        gemini_key = st.text_input("Gemini API Key", type="password", placeholder="AI-...")

    if ENV_HF_KEY:
        st.success("✅ Hugging Face Key 已設定")
        hf_key = ENV_HF_KEY
    else:
        hf_key = st.text_input("Hugging Face API Token", type="password", placeholder="hf_...")

    st.markdown("---")

    st.subheader("📚 閱讀設定")
    difficulty = st.selectbox(
        "閱讀年齡層",
        ["3-4 歲 (幼童)", "5-6 歲 (大班)", "7-8 歲 (初小)"],
    )
    generate_images = st.toggle("🎨 生成故事插圖 (Hugging Face 免費)", value=True)
    num_illustrations = st.slider("插圖數量", 1, 4, 2)

    st.markdown("---")
    st.caption("© 2025 AI 繪本故事生成器")

# ─────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────

def split_into_paragraphs(text: str, n: int) -> list[str]:
    """將故事文字切成 n 段，供插圖使用"""
    sentences = [s.strip() for s in text.replace("。", "。\n").split("\n") if s.strip()]
    if not sentences:
        return [text]
    chunk_size = max(1, len(sentences) // n)
    chunks = []
    for i in range(0, len(sentences), chunk_size):
        chunk = "".join(sentences[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks[:n]


def generate_hf_image(hf_key: str, scene_desc: str, character: str, scene: str) -> bytes | None:
    """呼叫 Hugging Face Stable Diffusion 生成插圖，回傳圖片 bytes"""
    prompt = (
        f"A charming children's picture book illustration in a soft watercolor style. "
        f"Scene: {scene_desc[:200]}. "
        f"The main character is '{character}', set in '{scene}'. "
        f"Bright friendly colors, no text, child-safe, storybook aesthetic."
    )
    headers = {"Authorization": f"Bearer {hf_key}"}
    payload = {
        "inputs": prompt,
        "parameters": {"width": 768, "height": 768, "num_inference_steps": 30},
    }
    try:
        resp = requests.post(HF_IMAGE_API, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
            return resp.content
        elif resp.status_code == 503:
            st.warning("⏳ 模型載入中，請稍後再試（約 20-30 秒）")
        else:
            st.warning(f"插圖生成失敗（{resp.status_code}）：{resp.text[:200]}")
        return None
    except Exception as e:
        st.warning(f"插圖生成失敗：{e}")
        return None


def url_to_base64(url: str) -> str | None:
    """把圖片 URL 轉成 base64（供 PDF 嵌入使用）"""
    try:
        r = requests.get(url, timeout=15)
        return base64.b64encode(r.content).decode()
    except Exception:
        return None


def create_pdf_report(history: list) -> bytes:
    """匯出閱讀紀錄 PDF 報告"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # 嘗試載入中文字型（若有放置 msjh.ttf）
    try:
        pdf.add_font("msjh", "", "msjh.ttf", uni=True)
        use_font = "msjh"
    except Exception:
        use_font = "Arial"

    pdf.set_font(use_font, size=20)
    pdf.cell(0, 14, "AI Storybook - Reading Report", ln=True, align="C")
    pdf.set_font(use_font, size=11)
    pdf.cell(0, 8, f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    pdf.ln(6)

    for i, item in enumerate(history, 1):
        pdf.set_font(use_font, size=13)
        pdf.set_fill_color(237, 231, 255)
        pdf.cell(0, 10, f"Story #{i}  |  {item.get('date', '')}  |  Theme: {item.get('theme', '')}", ln=True, fill=True)
        pdf.set_font(use_font, size=10)
        pdf.cell(0, 7, f"Character: {item.get('character', '')}   Scene: {item.get('scene', '')}   Level: {item.get('difficulty', '')}", ln=True)
        pdf.ln(2)
        pdf.set_font(use_font, size=10)
        pdf.multi_cell(0, 7, item.get("text", "")[:600] + ("..." if len(item.get("text", "")) > 600 else ""))
        pdf.ln(4)

    return bytes(pdf.output())


def create_story_pdf(text: str, character: str, image_bytes_list: list) -> bytes:
    """匯出單篇故事 PDF（含插圖）"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    try:
        pdf.add_font("msjh", "", "msjh.ttf", uni=True)
        use_font = "msjh"
    except Exception:
        use_font = "Arial"

    pdf.set_font(use_font, size=22)
    pdf.cell(0, 16, f"{character} 的專屬故事", ln=True, align="C")
    pdf.ln(4)

    # 嵌入第一張插圖（若有，直接用 bytes）
    if image_bytes_list:
        try:
            img_path = "/tmp/story_img_0.png"
            with open(img_path, "wb") as f:
                f.write(image_bytes_list[0])
            pdf.image(img_path, x=30, w=150)
            pdf.ln(4)
        except Exception:
            pass

    pdf.set_font(use_font, size=12)
    pdf.multi_cell(0, 8, text)

    return bytes(pdf.output())


def theme_chart(history: list) -> bytes:
    """畫主題統計圓餅圖，回傳 PNG bytes"""
    from collections import Counter
    counts = Counter(item["theme"] for item in history if "theme" in item)
    if not counts:
        return b""

    labels = list(counts.keys())
    values = list(counts.values())
    colors = ["#7C5CBF", "#F9A825", "#4CAF50", "#E91E63", "#2196F3", "#FF5722"]

    fig, ax = plt.subplots(figsize=(5, 4))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.0f%%",
        colors=colors[: len(labels)],
        startangle=140,
        pctdistance=0.82,
        wedgeprops={"linewidth": 2, "edgecolor": "white"},
    )
    for t in texts + autotexts:
        t.set_fontsize(11)
    ax.set_title("閱讀主題分佈", fontsize=14, pad=12)
    fig.patch.set_facecolor("#FDFAF6")
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def monthly_chart(history: list) -> bytes:
    """畫每月閱讀篇數長條圖，回傳 PNG bytes"""
    from collections import Counter
    months = []
    for item in history:
        d = item.get("date", "")
        if d:
            try:
                months.append(d[:7])  # YYYY-MM
            except Exception:
                pass
    if not months:
        return b""

    counts = Counter(months)
    labels = sorted(counts.keys())
    values = [counts[m] for m in labels]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(labels, values, color="#7C5CBF", edgecolor="white", linewidth=1.5, width=0.5)
    ax.set_title("每月閱讀篇數", fontsize=13)
    ax.set_ylabel("篇數")
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, str(v), ha="center", va="bottom", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.patch.set_facecolor("#FDFAF6")
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ─────────────────────────────────────────────
# 頁面：故事生成器
# ─────────────────────────────────────────────
if st.session_state.page == "generator":

    st.title("📖 AI 繪本故事生成器")
    st.markdown("##### 用 AI 發現問題，用創意改變生活。")
    st.markdown("---")

    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        st.subheader("🎭 故事設定")
        character = st.text_input(
            "主角是誰？",
            placeholder="例如：小兔兔、龍龍、你自己的名字…",
        )
        scene = st.text_input(
            "故事在哪裡發生？",
            placeholder="例如：魔法森林、海底世界、外太空…",
        )
        theme = st.selectbox(
            "今天想聽什麼主題？",
            ["友情", "勇氣", "冒險", "親情", "分享", "探索"],
        )

        generate_btn = st.button("✨ 開始生成專屬繪本", use_container_width=True, type="primary")

    with col_r:
        st.subheader("💡 使用提示")
        st.info(
            "**步驟說明**\n\n"
            "1. 輸入主角、場景與主題\n"
            "2. 點擊「開始生成」\n"
            "3. 故事與插圖將同步呈現\n"
            "4. 可匯出為 PDF 或前往家長儀表板查看統計"
        )
        if st.session_state.history:
            st.success(f"📚 已累積 **{len(st.session_state.history)}** 篇故事紀錄")

    # 生成邏輯
    if generate_btn:
        if not gemini_key:
            st.error("請先在左側邊欄輸入 Gemini API Key！")
        elif not character or not scene:
            st.warning("請填寫主角與場景，才能生成完整的故事喔！")
        else:
            with st.spinner("🔮 AI 正在為您創作故事…"):
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel("gemini-1.5-flash")

                    prompt = f"""
你是一位專為兒童寫作的繪本作家。
請為「{difficulty}」的孩子創作一篇關於「{theme}」的故事。
主角是「{character}」，故事發生在「{scene}」。
請用生動有趣、符合該年齡層的詞彙，長度約 400 到 600 字。
故事須分成 4 個段落（每段以空白行分隔），並帶有正向教育意義的結尾。
只輸出故事內容本身，不要加標題或編號。
"""
                    response = model.generate_content(prompt)
                    story_text = response.text.strip()
                    st.session_state.story_text = story_text
                    st.session_state.story_paragraphs = [
                        p.strip() for p in story_text.split("\n\n") if p.strip()
                    ]

                    # 儲存到歷史紀錄
                    record = {
                        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "character": character,
                        "scene": scene,
                        "theme": theme,
                        "difficulty": difficulty,
                        "text": story_text,
                    }
                    st.session_state.history.append(record)
                    st.session_state.current_meta = record

                except Exception as e:
                    st.error(f"故事生成失敗：{e}")
                    st.stop()

            # 生成插圖（Hugging Face 免費）
            st.session_state.image_urls = []   # 改存 bytes
            st.session_state.image_bytes = []
            if generate_images and hf_key:
                scenes_to_illustrate = split_into_paragraphs(
                    st.session_state.story_text, num_illustrations
                )
                prog = st.progress(0, text="🎨 正在生成插圖（免費模型，需約 30 秒）…")
                for idx, scene_desc in enumerate(scenes_to_illustrate):
                    img_data = generate_hf_image(hf_key, scene_desc, character, scene)
                    if img_data:
                        st.session_state.image_bytes.append(img_data)
                    prog.progress(
                        (idx + 1) / len(scenes_to_illustrate),
                        text=f"🎨 插圖 {idx+1}/{len(scenes_to_illustrate)} 完成",
                    )
                prog.empty()
            elif generate_images and not hf_key:
                st.warning("要生成插圖請在左側欄填入 Hugging Face API Token！")

    # 顯示故事結果
    if st.session_state.story_text:
        st.markdown("---")
        st.subheader("📚 你的專屬繪本")

        meta = st.session_state.current_meta
        if meta:
            st.markdown(
                f'<span class="badge">👤 {meta.get("character","")}</span>'
                f'<span class="badge">🌍 {meta.get("scene","")}</span>'
                f'<span class="badge">💡 {meta.get("theme","")}</span>'
                f'<span class="badge">📅 {meta.get("date","")}</span>',
                unsafe_allow_html=True,
            )
        st.markdown("")

        paragraphs = st.session_state.story_paragraphs
        image_bytes_list = st.session_state.image_bytes
        img_idx = 0

        for i, para in enumerate(paragraphs):
            # 每隔幾段插入一張圖
            if image_bytes_list and img_idx < len(image_bytes_list) and i % max(1, len(paragraphs) // len(image_bytes_list)) == 0:
                st.image(image_bytes_list[img_idx], use_container_width=True)
                img_idx += 1
            st.markdown(f'<div class="story-card">{para}</div>', unsafe_allow_html=True)

        # 若還有剩餘圖片放在最後
        while img_idx < len(image_bytes_list):
            st.image(image_bytes_list[img_idx], use_container_width=True)
            img_idx += 1

        st.markdown("---")

        # 匯出按鈕
        c1, c2, c3 = st.columns(3)
        with c1:
            story_pdf = create_story_pdf(
                st.session_state.story_text,
                meta.get("character", "故事"),
                st.session_state.image_bytes,
            )
            st.download_button(
                "🖨️ 匯出故事 PDF",
                data=story_pdf,
                file_name=f"{meta.get('character','story')}_繪本.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with c2:
            st.button("🔊 語音朗讀 (開發中)", use_container_width=True, disabled=True)
        with c3:
            if st.button("🔄 重新生成故事", use_container_width=True):
                st.session_state.story_text = ""
                st.session_state.story_paragraphs = []
                st.session_state.image_urls = []
                st.session_state.image_bytes = []
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

    # ── 統計數字 ──
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

    # ── 圖表區 ──
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("📊 主題分佈")
        chart_bytes = theme_chart(history)
        if chart_bytes:
            st.image(chart_bytes, use_container_width=True)

    with chart_col2:
        st.subheader("📅 每月閱讀篇數")
        monthly_bytes = monthly_chart(history)
        if monthly_bytes:
            st.image(monthly_bytes, use_container_width=True)
        else:
            st.info("需要多個月份的紀錄才能顯示此圖表。")

    st.markdown("---")

    # ── 閱讀紀錄列表 ──
    st.subheader("📋 閱讀紀錄")

    # 篩選器
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        all_themes = sorted({h["theme"] for h in history})
        selected_theme = st.selectbox("篩選主題", ["全部"] + all_themes)
    with filter_col2:
        sort_order = st.radio("排序", ["最新優先", "最舊優先"], horizontal=True)

    filtered = history if selected_theme == "全部" else [h for h in history if h["theme"] == selected_theme]
    if sort_order == "最新優先":
        filtered = list(reversed(filtered))

    for i, item in enumerate(filtered):
        with st.expander(
            f"📖 {item['character']} 在「{item['scene']}」的故事  ｜  {item['theme']}  ｜  {item['date']}"
        ):
            st.markdown(
                f'<span class="badge">📅 {item["date"]}</span>'
                f'<span class="badge">💡 {item["theme"]}</span>'
                f'<span class="badge">🎓 {item["difficulty"]}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown(f'<div class="story-card">{item["text"]}</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── 匯出報告 ──
    st.subheader("📄 匯出完整閱讀報告")
    report_pdf = create_pdf_report(history)
    st.download_button(
        "⬇️ 下載 PDF 學習報告",
        data=report_pdf,
        file_name=f"閱讀報告_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=False,
    )

    # ── 清除紀錄 ──
    st.markdown("---")
    if st.button("🗑️ 清除所有閱讀紀錄", type="secondary"):
        st.session_state.history = []
        st.session_state.story_text = ""
        st.session_state.story_paragraphs = []
        st.session_state.image_urls = []
        st.session_state.image_bytes = []
        st.success("已清除所有紀錄。")
        st.rerun()
