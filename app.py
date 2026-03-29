"""
🛒 ShortsCraft v2 - 쇼핑 쇼츠 자동 생성기
==========================================
쿠팡 링크 → 이미지 자동 추출 → AI 대본 → TTS 음성 → MP4 영상
실행: streamlit run app.py
"""
import streamlit as st
import os, json, tempfile, io, requests
from PIL import Image
from pathlib import Path

from script_engine import generate_with_claude, get_sample_script
from tts_engine import generate_scene_audios, cleanup_audio
from video_engine import generate_video

# ─── 페이지 설정 ──────────────────────────
st.set_page_config(
    page_title="ShortsCraft v2",
    page_icon="🛒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ─── CSS ──────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
.stApp { background-color: #0a0a0f; }
.main-header { text-align:center; padding:18px 0 8px; }
.main-header h1 {
    font-size:26px; font-weight:900;
    background:linear-gradient(90deg,#FFD700,#FF8C00);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.main-header p { color:#555; font-size:13px; margin-top:4px; }
.scene-card {
    background:#111118; border:1px solid #1a1a30;
    border-radius:12px; padding:14px; margin-bottom:8px;
}
.scene-badge {
    display:inline-block; padding:3px 10px; border-radius:6px;
    font-size:12px; font-weight:700; margin-right:8px;
}
.kw-badge {
    display:inline-block; background:rgba(255,215,0,.1);
    color:#FFD700; padding:2px 10px; border-radius:6px;
    font-size:12px; font-weight:700; float:right;
}
.stButton > button {
    background:linear-gradient(135deg,#FFD700,#FF8C00) !important;
    color:#000 !important; font-weight:800 !important;
    border:none !important; border-radius:12px !important;
    padding:12px !important; font-size:15px !important; width:100% !important;
}
.stButton > button:hover { opacity:.9 !important; }
.stDownloadButton > button {
    background:linear-gradient(135deg,#1a8a2a,#22aa33) !important;
    color:white !important; font-weight:700 !important;
    border:none !important; border-radius:12px !important;
}
div[data-testid="stFileUploader"] {
    background:#0e0e18; border:2px dashed #1c1c35;
    border-radius:14px; padding:10px;
}
</style>
""", unsafe_allow_html=True)

# ─── 상태 초기화 ──────────────────────────
for key in ["script", "video_path", "coupang_images"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ─── 헤더 ──────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🛒 ShortsCraft v2</h1>
    <p>쿠팡 링크 입력 → AI 대본 → TTS 음성 → MP4 쇼츠 자동 생성</p>
</div>
""", unsafe_allow_html=True)

# ─── 사이드바 ──────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ API 설정")
    anthropic_key = st.text_input("Claude API Key (선택)", type="password",
        help="없으면 샘플 대본 사용")
    elevenlabs_key = st.text_input("ElevenLabs API Key (선택)", type="password",
        help="없으면 gTTS(무료) 사용")
    st.markdown("---")
    st.markdown("### 💰 비용 안내")
    st.markdown("""
- **완전 무료**: gTTS + 샘플 대본
- **~₩50/건**: Claude API 대본
- **$5/월~**: ElevenLabs 고품질 음성
    """)

# ─── 쿠팡 이미지 추출 함수 ──────────────────
def fetch_coupang_images(url):
    """쿠팡 링크에서 제품 이미지 추출 시도"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return []
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        
        images = []
        # og:image
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            images.append(og["content"])
        
        # 제품 이미지
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if any(k in src for k in ["thumbnail", "product", "item"]) and src.startswith("http"):
                if src not in images:
                    images.append(src)
            if len(images) >= 5:
                break
        
        # 이미지 다운로드
        pil_images = []
        for url in images[:5]:
            try:
                r = requests.get(url, headers=headers, timeout=5)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                    pil_images.append(img)
            except:
                pass
        
        return pil_images
    except Exception as e:
        st.warning(f"이미지 추출 실패: {e}")
        return []

# ─── 탭 구성 ──────────────────────────
tab1, tab2, tab3 = st.tabs(["📷 영상 생성", "📝 대본 확인", "📥 다운로드"])

# ═══════════════════════════════════════
# 탭 1: 영상 생성
# ═══════════════════════════════════════
with tab1:
    # 이미지 소스 선택
    st.markdown("### 🖼️ 제품 이미지")
    img_source = st.radio(
        "이미지 소스",
        ["📎 쿠팡 링크에서 자동 추출", "📷 직접 업로드"],
        horizontal=True
    )
    
    coupang_link = ""
    uploaded_files = []
    
    if img_source == "📎 쿠팡 링크에서 자동 추출":
        coupang_link = st.text_input(
            "쿠팡파트너스 링크",
            placeholder="https://link.coupang.com/a/xxxxx",
            help="쿠팡 제품 페이지 또는 파트너스 링크"
        )
        if coupang_link and st.button("🔍 이미지 추출하기", key="fetch_img"):
            with st.spinner("쿠팡에서 이미지 가져오는 중..."):
                imgs = fetch_coupang_images(coupang_link)
                if imgs:
                    st.session_state.coupang_images = imgs
                    st.success(f"✅ {len(imgs)}장 추출 완료!")
                else:
                    st.warning("이미지 추출 실패. 직접 업로드해주세요.")
        
        # 추출된 이미지 미리보기
        if st.session_state.coupang_images:
            cols = st.columns(min(len(st.session_state.coupang_images), 5))
            for i, img in enumerate(st.session_state.coupang_images[:5]):
                with cols[i]:
                    st.image(img, caption=f"장면 {i+1}", use_container_width=True)
    else:
        uploaded_files = st.file_uploader(
            "제품 이미지 (여러 장 가능)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True
        )
        if uploaded_files:
            cols = st.columns(min(len(uploaded_files), 5))
            for i, file in enumerate(uploaded_files[:5]):
                with cols[i % 5]:
                    st.image(Image.open(file), caption=f"장면 {i+1}", use_container_width=True)
    
    st.markdown("---")
    
    # 제품 정보
    st.markdown("### 📦 제품 정보")
    c1, c2 = st.columns(2)
    with c1:
        product_name = st.text_input("제품명 *", placeholder="슈피겐 DA12 스타일러스 펜")
    with c2:
        product_price = st.text_input("가격", placeholder="12,000원")
    
    product_features = st.text_area(
        "주요 특징 *",
        placeholder="필압감지, 손바닥거부, 자석부착, USB-C 충전, 12시간 사용",
        height=80
    )
    
    c3, c4 = st.columns(2)
    with c3:
        target = st.text_input("타겟 고객", value="20~30대")
    with c4:
        duration = st.selectbox("영상 길이", [25, 35, 45], index=1,
                               format_func=lambda x: f"{x}초")
    
    st.markdown("---")
    
    # 후킹 스타일
    st.markdown("### 🎣 후킹 스타일")
    hook_map = {
        "충격형": "이 가격에 이 성능?",
        "질문형": "아직도 이거 안 써요?",
        "비교형": "5만원 vs 50만원 차이없음",
        "손실회피": "안 사면 후회할 3가지",
        "사회적증거": "100만명이 선택한 이유",
        "공감형": "저도 3번 고민했는데...",
    }
    hook_cols = st.columns(3)
    if "hook_style" not in st.session_state:
        st.session_state.hook_style = "충격형"
    
    for i, (style, desc) in enumerate(hook_map.items()):
        with hook_cols[i % 3]:
            if st.button(f"**{style}**\n{desc}", key=f"hk_{style}", use_container_width=True):
                st.session_state.hook_style = style
    
    st.info(f"선택: **{st.session_state.hook_style}**")
    
    st.markdown("---")
    
    # TTS
    st.markdown("### 🎙️ 음성 설정")
    tts_choice = st.radio(
        "TTS 엔진",
        ["gTTS (무료)", "ElevenLabs (고품질, $5/월~)"],
        horizontal=True
    )
    
    st.markdown("---")
    
    # 이미지 준비 여부 확인
    has_images = bool(uploaded_files) or bool(st.session_state.coupang_images)
    can_gen = product_name and product_features
    
    if not can_gen:
        st.warning("📝 제품명과 특징을 입력해주세요")
    if not has_images:
        st.info("🖼️ 이미지 없이도 생성 가능하지만, 이미지가 있으면 훨씬 좋아요!")
    
    # ═══ 생성 버튼 ═══
    if st.button("⚡ 쇼츠 영상 생성하기", disabled=not can_gen, use_container_width=True):
        progress = st.progress(0, text="준비 중...")
        
        # 1. 이미지 로드
        progress.progress(5, text="🖼️ 이미지 준비 중...")
        images = []
        
        if st.session_state.coupang_images:
            images = st.session_state.coupang_images
        elif uploaded_files:
            for file in uploaded_files:
                file.seek(0)
                images.append(Image.open(file).convert("RGBA"))
        
        # 이미지 없으면 그라데이션 배경 생성
        if not images:
            from PIL import ImageDraw as ID
            colors = [(255,60,60), (255,136,68), (68,187,255), (68,221,136), (255,214,68)]
            for c in colors:
                bg = Image.new("RGBA", (1080, 1920), (10, 10, 20, 255))
                d = ID.Draw(bg)
                for y in range(1920):
                    r = int(c[0] * (1 - y/1920) * 0.3 + 10)
                    g = int(c[1] * (1 - y/1920) * 0.3 + 10)
                    b = int(c[2] * (1 - y/1920) * 0.3 + 20)
                    d.line([(0, y), (1080, y)], fill=(r, g, b))
                images.append(bg)
            st.info("이미지 없이 그라데이션 배경으로 생성합니다")
        
        # 2. 대본 생성
        progress.progress(15, text="📝 AI 대본 생성 중...")
        if anthropic_key:
            script = generate_with_claude(
                product_name, product_price, product_features,
                target, st.session_state.hook_style, duration, anthropic_key
            )
        else:
            script = None
        
        if not script:
            script = get_sample_script(product_name, product_price, product_features, duration)
            if not anthropic_key:
                st.info("ℹ️ Claude API 키 없이 샘플 대본 사용")
        
        st.session_state.script = script
        
        # 3. TTS 생성
        progress.progress(30, text="🎙️ 음성 생성 중...")
        tts_type = "elevenlabs" if "ElevenLabs" in tts_choice and elevenlabs_key else "gtts"
        audio_files = generate_scene_audios(
            script["scenes"],
            tts_engine=tts_type,
            api_key=elevenlabs_key if tts_type == "elevenlabs" else None
        )
        
        # 4. 영상 생성
        safe_name = product_name[:10].replace(" ", "_").replace("/", "_")
        output_path = os.path.join(tempfile.gettempdir(), f"shorts_{safe_name}.mp4")
        
        def update_prog(p):
            pct = int(30 + p * 65)
            if p < 0.7:
                progress.progress(pct, text=f"🎬 프레임 생성 중... {int(p/0.7*100)}%")
            elif p < 0.85:
                progress.progress(pct, text="🎞️ FFmpeg 인코딩 중...")
            elif p < 1.0:
                progress.progress(pct, text="🔊 오디오 합성 중...")
            else:
                progress.progress(98, text="✅ 마무리 중...")
        
        success = generate_video(images, script, audio_files, output_path, update_prog)
        cleanup_audio()
        
        if success and os.path.exists(output_path):
            st.session_state.video_path = output_path
            progress.progress(100, text="🎉 영상 생성 완료!")
            st.success("✅ 영상이 생성되었습니다!")
            st.video(output_path)
            
            with open(output_path, "rb") as f:
                st.download_button(
                    "📥 MP4 다운로드",
                    data=f,
                    file_name=f"shorts_{safe_name}.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
        else:
            progress.progress(100, text="❌ 생성 실패")
            st.error("영상 생성 실패. FFmpeg가 설치되어 있는지 확인해주세요.\n`apt install ffmpeg` 또는 Streamlit Cloud에서는 packages.txt에 ffmpeg 추가")

# ═══════════════════════════════════════
# 탭 2: 대본 확인
# ═══════════════════════════════════════
with tab2:
    script = st.session_state.script
    if not script:
        st.info("📝 영상을 생성하면 대본이 여기에 표시됩니다")
    else:
        st.markdown(f"### 📺 {script.get('title', '')}")
        
        for i, scene in enumerate(script.get("scenes", [])):
            stype = scene.get("type", "")
            cmap = {"후킹":"#FF3B5C","문제제기":"#FF8844","제품소개":"#00D4FF","사회적증거":"#00E88C","CTA":"#FFD700"}
            color = cmap.get(stype, "#888")
            
            st.markdown(f"""
<div class="scene-card">
    <span class="scene-badge" style="background:{color}22;color:{color};">{i+1}. {stype}</span>
    <span style="color:#555;font-size:12px;">{scene.get('time','')}</span>
    <span class="kw-badge">{scene.get('keyword','')}</span>
    <div style="margin-top:10px;font-size:14px;line-height:1.6;color:#ccc;">{scene.get('narration','')}</div>
</div>
""", unsafe_allow_html=True)
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🏷️ 태그**")
            st.markdown(" ".join([f"`#{t}`" for t in script.get("tags", [])]))
        with c2:
            st.markdown("**🔑 SEO**")
            st.markdown(" ".join([f"`#{k}`" for k in script.get("seo_keywords", [])]))
        
        st.markdown("---")
        st.markdown("**📝 YouTube 설명란**")
        st.text_area("설명란 (복사해서 사용)", value=script.get("description", ""), height=120)
        
        st.download_button(
            "📋 전체 JSON 다운로드",
            data=json.dumps(script, ensure_ascii=False, indent=2),
            file_name="script.json",
            mime="application/json"
        )

# ═══════════════════════════════════════
# 탭 3: 다운로드
# ═══════════════════════════════════════
with tab3:
    vp = st.session_state.video_path
    if not vp or not os.path.exists(vp):
        st.info("📥 영상을 생성하면 여기서 다운로드")
    else:
        st.markdown("### 🎬 생성된 영상")
        st.video(vp)
        sz = os.path.getsize(vp) / 1024 / 1024
        st.markdown(f"📁 파일: **{sz:.1f}MB**")
        
        with open(vp, "rb") as f:
            st.download_button("📥 MP4 다운로드", data=f,
                file_name="shopping_shorts.mp4", mime="video/mp4",
                use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📋 YouTube 업로드 체크리스트")
        st.checkbox("제목 복사 완료")
        st.checkbox("설명란 + 쿠팡 링크 복사 완료")
        st.checkbox("태그 입력 완료")
        st.checkbox("공개 설정 확인")
