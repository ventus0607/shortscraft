"""
🛒 ShortsCraft - 쇼핑 쇼츠 자동 생성기
========================================
실행: streamlit run app.py
"""
import streamlit as st
import os, json, tempfile
from PIL import Image
from pathlib import Path

# 모듈 임포트
from script_engine import generate_with_claude, get_sample_script
from tts_engine import generate_scene_audios, cleanup_audio
from video_engine import generate_video

# ─── 페이지 설정 ──────────────────────────
st.set_page_config(
    page_title="ShortsCraft - 쇼핑 쇼츠 생성기",
    page_icon="🛒",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ─── 커스텀 CSS ──────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    
    .stApp { background-color: #0a0a0f; color: #cccccc; }
    
    .main-title {
        text-align: center;
        padding: 20px 0 5px;
    }
    .main-title h1 {
        font-size: 28px;
        font-weight: 800;
        background: linear-gradient(90deg, #FF4422, #FFDD00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .main-title p {
        color: #555;
        font-size: 14px;
        margin-top: 5px;
    }
    
    .scene-card {
        background: #111118;
        border: 1px solid #1a1a30;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 8px;
    }
    .scene-type {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        margin-right: 8px;
    }
    .keyword-badge {
        display: inline-block;
        background: rgba(255,221,0,0.1);
        color: #FFDD00;
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        float: right;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(135deg, #c02818, #e84828) !important;
        color: white !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-size: 16px !important;
        width: 100% !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #a02010, #c83818) !important;
    }
    
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1a8a2a, #22aa33) !important;
        color: white !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
    }
    
    div[data-testid="stFileUploader"] {
        background: #0e0e18;
        border: 2px dashed #1c1c35;
        border-radius: 14px;
        padding: 10px;
    }
    
    .stSelectbox > div > div { background: #0e0e18; }
    .stTextInput > div > div > input { background: #0e0e18; color: #ddd; }
    .stTextArea > div > div > textarea { background: #0e0e18; color: #ddd; }
</style>
""", unsafe_allow_html=True)

# ─── 상태 초기화 ──────────────────────────
if "script" not in st.session_state:
    st.session_state.script = None
if "video_path" not in st.session_state:
    st.session_state.video_path = None

# ─── 헤더 ──────────────────────────────
st.markdown("""
<div class="main-title">
    <h1>🛒 ShortsCraft</h1>
    <p>이미지 업로드 → AI 대본 → TTS 음성 → 쇼츠 영상 자동 생성</p>
</div>
""", unsafe_allow_html=True)

# ─── 사이드바: API 설정 ──────────────────
with st.sidebar:
    st.markdown("### ⚙️ API 설정")
    
    anthropic_key = st.text_input(
        "Claude API Key (선택)", 
        type="password",
        help="없으면 샘플 대본을 사용합니다"
    )
    
    elevenlabs_key = st.text_input(
        "ElevenLabs API Key (선택)", 
        type="password",
        help="없으면 gTTS(무료)를 사용합니다"
    )
    
    st.markdown("---")
    st.markdown("### 💡 설치 방법")
    st.code("pip install -r requirements.txt\nstreamlit run app.py", language="bash")
    
    st.markdown("### 💰 비용")
    st.markdown("""
    - **무료**: gTTS + 샘플 대본
    - **₩50/건**: Claude API (대본)
    - **$5/월**: ElevenLabs (음성)
    """)

# ─── 탭 구성 ──────────────────────────
tab1, tab2, tab3 = st.tabs(["📷 영상 생성", "📝 대본 확인", "📥 다운로드"])

# ═══════════════════════════════════════
# 탭 1: 영상 생성
# ═══════════════════════════════════════
with tab1:
    
    # 이미지 업로드
    st.markdown("### 🖼️ 제품 이미지 업로드")
    uploaded_files = st.file_uploader(
        "제품 이미지를 올려주세요 (여러 장 가능)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="쿠팡/네이버에서 저장한 제품 이미지. 장면 수만큼 올리면 각각 다른 이미지가 사용됩니다."
    )
    
    # 업로드된 이미지 미리보기
    if uploaded_files:
        cols = st.columns(min(len(uploaded_files), 5))
        for i, file in enumerate(uploaded_files[:5]):
            with cols[i % 5]:
                img = Image.open(file)
                st.image(img, caption=f"장면 {i+1}", use_container_width=True)
    
    st.markdown("---")
    
    # 제품 정보 입력
    st.markdown("### 📦 제품 정보")
    
    col1, col2 = st.columns(2)
    with col1:
        product_name = st.text_input("제품명 *", placeholder="슈피겐 아이패드 터치펜 DA12")
    with col2:
        product_price = st.text_input("가격", placeholder="12,000원")
    
    product_features = st.text_area(
        "주요 특징 *", 
        placeholder="필압감지, 손바닥거부, 자석부착, USB-C 충전, 12시간 사용",
        height=80
    )
    
    col3, col4 = st.columns(2)
    with col3:
        target = st.text_input("타겟 고객", value="20~30대")
    with col4:
        duration = st.selectbox("영상 길이", [25, 35, 45], index=1, format_func=lambda x: f"{x}초")
    
    st.markdown("---")
    
    # 스타일 설정
    st.markdown("### 🎣 후킹 스타일")
    hook_options = {
        "충격형": "이 가격에 이 성능?",
        "질문형": "아직도 이거 안 쓰세요?",
        "비교형": "5만원 vs 50만원 차이없음",
        "손실회피": "안 사면 후회할 3가지",
        "사회적증거": "100만명이 선택한 이유",
        "공감형": "저도 3번 고민했는데...",
    }
    
    hook_cols = st.columns(3)
    hook_style = "비교형"
    for i, (style, desc) in enumerate(hook_options.items()):
        with hook_cols[i % 3]:
            if st.button(f"**{style}**\n{desc}", key=f"hook_{style}", use_container_width=True):
                hook_style = style
    
    st.markdown("---")
    
    # TTS 설정
    st.markdown("### 🎙️ 음성 설정")
    tts_engine = st.radio(
        "TTS 엔진",
        ["gTTS (무료, 기본 품질)", "ElevenLabs (고품질, API 키 필요)"],
        horizontal=True
    )
    
    st.markdown("---")
    
    # ═══ 생성 버튼 ═══
    can_generate = uploaded_files and product_name and product_features
    
    if not can_generate:
        st.warning("📷 이미지와 📝 제품명/특징을 입력해주세요")
    
    if st.button("✨ 쇼츠 영상 생성하기", disabled=not can_generate, use_container_width=True):
        
        progress = st.progress(0, text="준비 중...")
        
        # 1. 이미지 로드
        progress.progress(5, text="🖼️ 이미지 로드 중...")
        images = []
        for file in uploaded_files:
            file.seek(0)
            img = Image.open(file).convert("RGBA")
            images.append(img)
        
        # 2. 대본 생성
        progress.progress(15, text="📝 AI 대본 생성 중...")
        
        if anthropic_key:
            script = generate_with_claude(
                product_name, product_price, product_features,
                target, hook_style, duration, anthropic_key
            )
        else:
            script = None
        
        if not script:
            script = get_sample_script(product_name, product_price, product_features, duration)
            st.info("ℹ️ Claude API 키가 없어 샘플 대본을 사용합니다")
        
        st.session_state.script = script
        
        # 3. TTS 생성
        progress.progress(30, text="🎙️ TTS 음성 생성 중...")
        
        tts_type = "elevenlabs" if "ElevenLabs" in tts_engine and elevenlabs_key else "gtts"
        audio_files = generate_scene_audios(
            script["scenes"], 
            tts_engine=tts_type,
            api_key=elevenlabs_key if tts_type == "elevenlabs" else None
        )
        
        # 4. 영상 생성
        output_path = f"output_{product_name[:10].replace(' ','_')}.mp4"
        
        def update_progress(p):
            pct = int(30 + p * 65)
            if p < 0.7:
                progress.progress(pct, text=f"🎬 프레임 생성 중... {int(p/0.7*100)}%")
            elif p < 0.85:
                progress.progress(pct, text="🎞️ FFmpeg 인코딩 중...")
            elif p < 1.0:
                progress.progress(pct, text="🔊 오디오 합성 중...")
            else:
                progress.progress(98, text="✅ 마무리 중...")
        
        success = generate_video(images, script, audio_files, output_path, update_progress)
        
        # 정리
        cleanup_audio()
        
        if success:
            st.session_state.video_path = output_path
            progress.progress(100, text="🎉 영상 생성 완료!")
            st.success(f"✅ 영상이 생성되었습니다!")
            
            # 영상 미리보기
            st.video(output_path)
            
            # 다운로드 버튼
            with open(output_path, "rb") as f:
                st.download_button(
                    "📥 MP4 다운로드",
                    data=f,
                    file_name=f"shorts_{product_name[:15]}.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )
        else:
            progress.progress(100, text="❌ 생성 실패")
            st.error("영상 생성에 실패했습니다. FFmpeg가 설치되어 있는지 확인해주세요.")


# ═══════════════════════════════════════
# 탭 2: 대본 확인
# ═══════════════════════════════════════
with tab2:
    script = st.session_state.script
    
    if not script:
        st.info("📝 영상을 생성하면 대본이 여기에 표시됩니다")
    else:
        st.markdown(f"### 📺 {script.get('title', '')}")
        
        # 장면별 대본
        for i, scene in enumerate(script.get("scenes", [])):
            stype = scene.get("type", "")
            color_map = {"후킹":"#FF4444","문제제기":"#FF8844","제품소개":"#44BBFF","사회적증거":"#44DD88","CTA":"#FFD644"}
            color = color_map.get(stype, "#888")
            
            st.markdown(f"""
            <div class="scene-card">
                <span class="scene-type" style="background:{color}22;color:{color};">{stype}</span>
                <span style="color:#555;font-size:12px;">{scene.get('time','')}</span>
                <span class="keyword-badge">{scene.get('keyword','')}</span>
                <div style="margin-top:10px;font-size:14px;line-height:1.6;color:#ccc;">{scene.get('narration','')}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 태그 & SEO
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🏷️ 태그**")
            tags = script.get("tags", [])
            st.markdown(" ".join([f"`#{t}`" for t in tags]))
        with col2:
            st.markdown("**🔑 SEO 키워드**")
            keywords = script.get("seo_keywords", [])
            st.markdown(" ".join([f"`#{k}`" for k in keywords]))
        
        # 설명란
        st.markdown("---")
        st.markdown("**📝 YouTube 설명란**")
        desc = script.get("description", "")
        st.text_area("설명란 (복사해서 사용)", value=desc, height=100)
        
        # JSON 내보내기
        st.markdown("---")
        st.download_button(
            "📋 전체 대본 JSON 다운로드",
            data=json.dumps(script, ensure_ascii=False, indent=2),
            file_name="script.json",
            mime="application/json"
        )


# ═══════════════════════════════════════
# 탭 3: 다운로드
# ═══════════════════════════════════════
with tab3:
    video_path = st.session_state.video_path
    
    if not video_path or not os.path.exists(video_path):
        st.info("📥 영상을 생성하면 여기서 다운로드할 수 있습니다")
    else:
        st.markdown("### 🎬 생성된 영상")
        st.video(video_path)
        
        file_size = os.path.getsize(video_path) / 1024 / 1024
        st.markdown(f"📁 파일 크기: **{file_size:.1f}MB**")
        
        with open(video_path, "rb") as f:
            st.download_button(
                "📥 MP4 다운로드",
                data=f,
                file_name="shopping_shorts.mp4",
                mime="video/mp4",
                use_container_width=True
            )
        
        st.markdown("---")
        st.markdown("### 📋 YouTube 업로드 체크리스트")
        st.checkbox("제목 복사 완료")
        st.checkbox("설명란 복사 완료")
        st.checkbox("태그 입력 완료")
        st.checkbox("쇼핑 제품 태그 설정")
        st.checkbox("공개 설정 확인")
        
        st.markdown("---")
        st.markdown("### 💡 다음 단계")
        st.markdown("""
        1. **YouTube Studio** → Shorts 업로드
        2. 대본 탭의 **제목/설명/태그** 복사해서 입력
        3. **쿠팡 파트너스** 링크를 설명란/댓글에 추가
        4. 업로드 시간: **오후 6~9시** (피크 시간대)
        """)


# ─── 하단 정보 ──────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#333;font-size:11px;'>"
    "ShortsCraft v1.0 · 이미지만 올리면 쇼핑 쇼츠 자동 생성 · "
    "Python + Pillow + FFmpeg + gTTS"
    "</div>",
    unsafe_allow_html=True
)
