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
    
    /* ✨ 修復版：Slogan 動態文字特效 (拆分內外層) ✨ */
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
