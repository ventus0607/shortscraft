"""
TTS 엔진 - gTTS(무료) / ElevenLabs(유료)
"""
import os, tempfile

_audio_files = []

def generate_scene_audios(scenes, tts_engine="gtts", api_key=None):
    """각 장면의 나레이션으로 오디오 파일 생성"""
    global _audio_files
    _audio_files = []
    
    for i, scene in enumerate(scenes):
        text = scene.get("narration", "")
        if not text.strip():
            _audio_files.append(None)
            continue
        
        path = os.path.join(tempfile.gettempdir(), f"sc_tts_{i}.mp3")
        
        try:
            if tts_engine == "elevenlabs" and api_key:
                _generate_elevenlabs(text, path, api_key)
            else:
                _generate_gtts(text, path)
            _audio_files.append(path)
        except Exception as e:
            print(f"TTS error scene {i}: {e}")
            # Fallback to gTTS
            try:
                _generate_gtts(text, path)
                _audio_files.append(path)
            except:
                _audio_files.append(None)
    
    return _audio_files

def _generate_gtts(text, path):
    """gTTS로 한국어 음성 생성"""
    from gtts import gTTS
    tts = gTTS(text=text, lang='ko', slow=False)
    tts.save(path)

def _generate_elevenlabs(text, path, api_key):
    """ElevenLabs API로 고품질 음성 생성"""
    import requests
    
    # 한국어 지원 음성 ID (Rachel - multilingual)
    voice_id = "21m00Tcm4TlvDq8ikWAM"
    
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
    )
    
    if resp.status_code == 200:
        with open(path, "wb") as f:
            f.write(resp.content)
    else:
        raise Exception(f"ElevenLabs API error: {resp.status_code}")

def cleanup_audio():
    """임시 오디오 파일 정리"""
    global _audio_files
    for path in _audio_files:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
    _audio_files = []
