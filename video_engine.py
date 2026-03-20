"""영상 생성 엔진 - 이미지 + 자막 + 효과 → MP4"""
import os, subprocess, math
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 24

SCENE_COLORS = {
    "후킹": "#FF4444", "문제제기": "#FF8844",
    "제품소개": "#44BBFF", "사회적증거": "#44DD88", "CTA": "#FFD644"
}

FONT_PATHS = [
    "fonts/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]

def get_font(size):
    for fp in FONT_PATHS:
        if os.path.exists(fp):
            try: return ImageFont.truetype(fp, size)
            except: continue
    return ImageFont.load_default()

def split_chunks(text, max_len=8):
    words = text.replace(",", " ").replace(".", " ").split()
    chunks, buf = [], ""
    for w in words:
        if len(buf + " " + w) > max_len and buf:
            chunks.append(buf.strip())
            buf = w
        else:
            buf = (buf + " " + w).strip()
    if buf: chunks.append(buf)
    return chunks if chunks else [text[:max_len]]

def generate_video(images, script, audio_files, output_path, progress_callback=None):
    """
    이미지 + 대본 + 오디오 → MP4 영상 생성
    
    Args:
        images: PIL Image 리스트
        script: 대본 dict (scenes 포함)
        audio_files: 장면별 오디오 파일 경로 리스트
        output_path: 출력 MP4 경로
        progress_callback: 진행률 콜백 함수 (0.0~1.0)
    """
    scenes = script["scenes"]
    durations = []
    for s in scenes:
        m = (s.get("time","") or "").replace("초","")
        parts = m.split("-")
        if len(parts) == 2:
            try: durations.append(int(parts[1]) - int(parts[0]))
            except: durations.append(5)
        else:
            durations.append(5)
    
    total_frames = sum(d * FPS for d in durations)
    
    # 폰트 로드
    sub_font = get_font(80)
    narr_font = get_font(32)
    badge_font = get_font(24)
    
    # 임시 디렉토리
    frame_dir = "temp_frames"
    os.makedirs(frame_dir, exist_ok=True)
    
    frame_num = 0
    for si, (scene, dur) in enumerate(zip(scenes, durations)):
        scene_frames = dur * FPS
        img = images[si % len(images)]
        chunks = split_chunks(scene.get("narration", ""))
        
        for fi in range(scene_frames):
            t = fi / max(scene_frames - 1, 1)
            
            # === Ken Burns 효과 ===
            zoom = 1.15 + t * 0.2
            iw, ih = img.size
            ratio = max(W/iw, H/ih) * zoom
            nw, nh = int(iw*ratio), int(ih*ratio)
            resized = img.resize((nw, nh), Image.LANCZOS)
            cx = max(0, min((nw-W)//2 + int(t*20-10), nw-W))
            cy = max(0, min((nh-H)//2 + int(t*15-7), nh-H))
            frame = resized.crop((cx, cy, cx+W, cy+H))
            if frame.mode != "RGBA": frame = frame.convert("RGBA")
            
            # === 어두운 오버레이 ===
            ov = Image.new("RGBA", (W, H), (0,0,0,0))
            dov = ImageDraw.Draw(ov)
            for y in range(H):
                if y < H*0.25: a = int(70*(1-y/(H*0.25)))
                elif y > H*0.6: a = int(200*((y-H*0.6)/(H*0.4)))
                else: a = 5
                dov.line([(0,y),(W,y)], fill=(0,0,0,min(a,220)))
            frame = Image.alpha_composite(frame, ov)
            draw = ImageDraw.Draw(frame)
            
            # === 큰 노란 자막 (빠른 전환) ===
            chunk_dur = scene_frames / len(chunks)
            ci = min(int(fi / chunk_dur), len(chunks)-1)
            chunk = chunks[ci]
            
            bbox = draw.textbbox((0,0), chunk, font=sub_font)
            tw = bbox[2]-bbox[0]
            sx, sy = (W-tw)//2, int(H*0.42)
            for dx in range(-5,6):
                for dy in range(-5,6):
                    if dx*dx+dy*dy <= 25:
                        draw.text((sx+dx,sy+dy), chunk, fill="#000000", font=sub_font)
            draw.text((sx, sy), chunk, fill="#FFDD00", font=sub_font)
            
            # === 장면 뱃지 ===
            color = SCENE_COLORS.get(scene.get("type",""), "#888")
            label = f"{si+1}/{len(scenes)}  {scene.get('type','')}"
            bl = draw.textbbox((0,0), label, font=badge_font)
            btw = bl[2]-bl[0]
            draw.rounded_rectangle([(30,30),(30+btw+24,30+40)], radius=20, fill=color)
            draw.text((42, 36), label, fill="#FFFFFF", font=badge_font)
            
            # === 하단 나레이션 바 ===
            narr = scene.get("narration", "")
            draw.rounded_rectangle([(30,H-200),(W-30,H-100)], radius=15, fill=(0,0,0,180))
            lines = [narr[i:i+25] for i in range(0, min(len(narr),50), 25)]
            ny = H-190
            for line in lines:
                b = draw.textbbox((0,0), line, font=narr_font)
                draw.text(((W-b[2]+b[0])//2, ny), line, fill="#FFFFFF", font=narr_font)
                ny += 38
            
            # === 프로그레스 바 ===
            bar_y = H - 50
            seg_w = (W-80-8*(len(scenes)-1))/len(scenes)
            for i in range(len(scenes)):
                x = 40 + i*(seg_w+8)
                draw.rounded_rectangle([(x,bar_y),(x+seg_w,bar_y+6)], radius=3, fill=(255,255,255,40))
                p = 1.0 if i < si else (t if i == si else 0)
                if p > 0:
                    c = "#FFDD00" if i==si else "#FFFFFF"
                    draw.rounded_rectangle([(x,bar_y),(x+seg_w*p,bar_y+6)], radius=3, fill=c)
            
            # 저장
            frame.convert("RGB").save(f"{frame_dir}/frame_{frame_num:06d}.jpg", quality=85)
            frame_num += 1
            
            if progress_callback and frame_num % (FPS*2) == 0:
                progress_callback(frame_num / total_frames * 0.7)  # 70%까지 프레임 생성
    
    # === FFmpeg 인코딩 ===
    if progress_callback: progress_callback(0.75)
    
    video_only = "temp_video.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", f"{frame_dir}/frame_%06d.jpg",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "25", video_only
    ], capture_output=True)
    
    # === 오디오 합성 ===
    valid_audios = [a for a in audio_files if a and os.path.exists(a)]
    
    if valid_audios:
        if progress_callback: progress_callback(0.85)
        
        list_file = "temp_audiolist.txt"
        with open(list_file, "w") as f:
            for a in audio_files:
                if a and os.path.exists(a):
                    f.write(f"file '{os.path.abspath(a)}'\n")
        
        combined = "temp_combined.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c:a", "libmp3lame", combined
        ], capture_output=True)
        
        subprocess.run([
            "ffmpeg", "-y", "-i", video_only, "-i", combined,
            "-c:v", "copy", "-c:a", "aac", "-shortest", output_path
        ], capture_output=True)
        
        for f in [list_file, combined]: 
            if os.path.exists(f): os.remove(f)
    else:
        os.rename(video_only, output_path)
    
    # 정리
    if os.path.exists(video_only) and os.path.exists(output_path):
        try: os.remove(video_only)
        except: pass
    
    import shutil
    shutil.rmtree(frame_dir, ignore_errors=True)
    
    if progress_callback: progress_callback(1.0)
    
    return os.path.exists(output_path)
