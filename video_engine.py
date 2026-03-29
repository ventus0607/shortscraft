"""
영상 생성 엔진 - Pillow + FFmpeg
9:16 세로 영상 (1080x1920) with Ken Burns, 자막, 뱃지
"""
import os, subprocess, tempfile, math
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30

# Ken Burns 패턴
KB_PATTERNS = [
    {"name": "zoom_in", "s0": 1.0, "s1": 1.3, "dx": 0, "dy": -0.05},
    {"name": "zoom_out", "s0": 1.3, "s1": 1.0, "dx": 0, "dy": 0.05},
    {"name": "pan_right", "s0": 1.2, "s1": 1.2, "dx": 0.15, "dy": 0},
    {"name": "pan_up", "s0": 1.15, "s1": 1.15, "dx": 0, "dy": -0.12},
    {"name": "drift", "s0": 1.1, "s1": 1.25, "dx": 0.08, "dy": -0.06},
]

SCENE_COLORS = {
    "후킹": (255, 60, 60),
    "문제제기": (255, 136, 68),
    "제품소개": (68, 187, 255),
    "사회적증거": (68, 221, 136),
    "CTA": (255, 214, 68),
}

def _get_font(size, bold=False):
    """한국어 폰트 로드"""
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansKR-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                pass
    return ImageFont.load_default()

def _apply_ken_burns(img, pattern_idx, progress):
    """Ken Burns 효과 적용"""
    pat = KB_PATTERNS[pattern_idx % len(KB_PATTERNS)]
    t = progress
    scale = pat["s0"] + (pat["s1"] - pat["s0"]) * t
    dx = pat["dx"] * t
    dy = pat["dy"] * t
    
    # 이미지를 9:16으로 크롭 후 스케일
    iw, ih = img.size
    target_ratio = W / H
    img_ratio = iw / ih
    
    if img_ratio > target_ratio:
        new_h = ih
        new_w = int(ih * target_ratio)
    else:
        new_w = iw
        new_h = int(iw / target_ratio)
    
    cx, cy = iw / 2 + dx * iw, ih / 2 + dy * ih
    crop_w, crop_h = new_w / scale, new_h / scale
    
    x1 = max(0, int(cx - crop_w / 2))
    y1 = max(0, int(cy - crop_h / 2))
    x2 = min(iw, int(cx + crop_w / 2))
    y2 = min(ih, int(cy + crop_h / 2))
    
    cropped = img.crop((x1, y1, x2, y2))
    return cropped.resize((W, H), Image.LANCZOS)

def _draw_subtitle(draw, text, y_pos, font_size=72):
    """큰 노란 자막 (검은 외곽선)"""
    font = _get_font(font_size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    
    # 검은 외곽선
    for ox in range(-4, 5, 2):
        for oy in range(-4, 5, 2):
            draw.text((x + ox, y_pos + oy), text, fill=(0, 0, 0), font=font)
    # 노란 글자
    draw.text((x, y_pos), text, fill=(255, 215, 0), font=font)

def _draw_badge(draw, scene_type, y=80):
    """장면 타입 뱃지"""
    color = SCENE_COLORS.get(scene_type, (128, 128, 128))
    font = _get_font(28)
    text = f"  {scene_type}  "
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # 반투명 배경
    x = 40
    draw.rounded_rectangle(
        [(x, y), (x + tw + 20, y + th + 16)],
        radius=12,
        fill=(*color, 60),
        outline=(*color, 120),
        width=2
    )
    draw.text((x + 10, y + 8), text, fill=(*color, 255), font=font)

def _draw_progress_bar(draw, progress, total_progress, color):
    """하단 프로그레스 바"""
    # 장면 프로그레스
    bar_y = H - 120
    draw.rectangle([(0, bar_y), (W, bar_y + 6)], fill=(40, 40, 60))
    draw.rectangle([(0, bar_y), (int(W * progress), bar_y + 6)], fill=color)
    
    # 전체 프로그레스
    bar_y2 = H - 108
    draw.rectangle([(0, bar_y2), (W, bar_y2 + 4)], fill=(30, 30, 50))
    draw.rectangle([(0, bar_y2), (int(W * total_progress), bar_y2 + 4)], fill=(255, 255, 255, 80))

def _draw_narration_bar(draw, text, y=H - 200):
    """나레이션 텍스트 바"""
    font = _get_font(28)
    # 반투명 배경
    draw.rectangle([(20, y), (W - 20, y + 60)], fill=(0, 0, 0, 140))
    # 텍스트 (길면 자름)
    display = text[:35] + "..." if len(text) > 35 else text
    draw.text((40, y + 15), display, fill=(200, 200, 200), font=font)

def generate_video(images, script, audio_files, output_path, progress_cb=None):
    """메인 영상 생성 함수"""
    scenes = script.get("scenes", [])
    if not scenes:
        return False
    
    tmp_dir = tempfile.mkdtemp(prefix="sc_frames_")
    frame_idx = 0
    total_frames = sum(s.get("duration", 5) * FPS for s in scenes)
    
    # 자막 청크 분할
    def chunk_text(text, max_len=7):
        if not text:
            return [""]
        words = text.replace(",", " ").replace(".", " ").replace("!", " ").strip().split()
        chunks = []
        cur = ""
        for w in words:
            if len(cur + w) > max_len and cur:
                chunks.append(cur.strip())
                cur = w
            else:
                cur += (" " if cur else "") + w
        if cur.strip():
            chunks.append(cur.strip())
        return chunks if chunks else [""]
    
    accumulated = 0
    
    for si, scene in enumerate(scenes):
        dur = scene.get("duration", 5)
        scene_frames = dur * FPS
        stype = scene.get("type", "제품소개")
        color = SCENE_COLORS.get(stype, (128, 128, 128))
        narration = scene.get("narration", "")
        keyword = scene.get("keyword", "")
        
        # 자막 청크
        chunks = chunk_text(keyword, 7)
        chunk_dur = scene_frames / max(len(chunks), 1)
        
        # 이미지 선택 (순환)
        img = images[si % len(images)] if images else None
        
        for fi in range(scene_frames):
            progress = fi / scene_frames
            total_progress = (accumulated + fi) / total_frames
            
            # 프레임 생성
            if img:
                frame = _apply_ken_burns(img, si, progress)
            else:
                frame = Image.new("RGBA", (W, H), (10, 10, 20, 255))
            
            frame = frame.convert("RGBA")
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # 하단 그라데이션
            for gy in range(400):
                alpha = int(180 * (gy / 400))
                draw.rectangle([(0, H - 400 + gy), (W, H - 400 + gy + 1)], fill=(0, 0, 0, alpha))
            
            # 뱃지
            _draw_badge(draw, stype)
            
            # 큰 노란 자막
            ci = min(int(fi / chunk_dur), len(chunks) - 1)
            _draw_subtitle(draw, chunks[ci], H - 450, font_size=80)
            
            # 나레이션 바
            _draw_narration_bar(draw, narration)
            
            # 프로그레스 바
            _draw_progress_bar(draw, progress, total_progress, color)
            
            # 합성
            frame = Image.alpha_composite(frame, overlay)
            frame = frame.convert("RGB")
            
            frame_path = os.path.join(tmp_dir, f"frame_{frame_idx:06d}.png")
            frame.save(frame_path, "PNG")
            frame_idx += 1
            
            if progress_cb and fi % (FPS * 2) == 0:
                progress_cb(total_progress * 0.7)
        
        accumulated += scene_frames
    
    if progress_cb:
        progress_cb(0.7)
    
    # FFmpeg: 프레임 → 영상
    frames_pattern = os.path.join(tmp_dir, "frame_%06d.png")
    temp_video = os.path.join(tmp_dir, "temp.mp4")
    
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", frames_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "23",
        temp_video
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
    except Exception as e:
        print(f"FFmpeg error: {e}")
        return False
    
    if progress_cb:
        progress_cb(0.85)
    
    # 오디오 합성
    valid_audios = [a for a in (audio_files or []) if a and os.path.exists(a)]
    
    if valid_audios:
        # 오디오 파일들을 concat
        concat_list = os.path.join(tmp_dir, "audio_list.txt")
        with open(concat_list, "w") as f:
            for ap in valid_audios:
                f.write(f"file '{ap}'\n")
        
        merged_audio = os.path.join(tmp_dir, "merged.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-c:a", "libmp3lame", merged_audio
        ], capture_output=True, timeout=60)
        
        if os.path.exists(merged_audio):
            # 영상 + 오디오 합성
            subprocess.run([
                "ffmpeg", "-y",
                "-i", temp_video,
                "-i", merged_audio,
                "-c:v", "copy", "-c:a", "aac",
                "-shortest",
                output_path
            ], capture_output=True, timeout=60)
        else:
            os.rename(temp_video, output_path)
    else:
        os.rename(temp_video, output_path)
    
    if progress_cb:
        progress_cb(1.0)
    
    # 정리
    import shutil
    try:
        shutil.rmtree(tmp_dir)
    except:
        pass
    
    return os.path.exists(output_path)
