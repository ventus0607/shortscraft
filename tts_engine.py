"""TTS 음성 생성 엔진"""
import os

def generate_tts_gtts(text, output_path, lang="ko"):
    """gTTS로 음성 생성 (무료)"""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_path)
        return True
    except Exception as e:
        print(f"gTTS 오류: {e}")
        return False

def generate_tts_elevenlabs(text, output_path, api_key, voice_id=None):
    """ElevenLabs로 음성 생성 (고품질)"""
    try:
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        
        if not voice_id:
            # 한국어 음성 자동 선택
            voices = client.voices.get_all()
            ko_voice = next((v for v in voices.voices if "korean" in str(v.labels).lower()), None)
            voice_id = ko_voice.voice_id if ko_voice else "21m00Tcm4TlvDq8ikWAM"
        
        audio = client.text_to_speech.convert(
            text=text, voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        with open(output_path, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        return True
    except Exception as e:
        print(f"ElevenLabs 오류: {e}")
        return False

def generate_scene_audios(scenes, tts_engine="gtts", api_key=None):
    """모든 장면의 TTS 음성을 생성합니다."""
    os.makedirs("temp_audio", exist_ok=True)
    audio_files = []
    
    for i, scene in enumerate(scenes):
        path = f"temp_audio/scene_{i}.mp3"
        text = scene.get("narration", "")
        
        if not text:
            audio_files.append(None)
            continue
        
        if tts_engine == "elevenlabs" and api_key:
            ok = generate_tts_elevenlabs(text, path, api_key)
        else:
            ok = generate_tts_gtts(text, path)
        
        audio_files.append(path if ok else None)
    
    return audio_files

def cleanup_audio():
    """임시 오디오 파일 정리"""
    import shutil
    shutil.rmtree("temp_audio", ignore_errors=True)
