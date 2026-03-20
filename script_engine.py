"""AI 대본 생성 엔진"""
import json

def generate_with_claude(product_name, price, features, target, hook_style, duration, api_key):
    """Claude API로 대본 생성"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""유튜브 쇼핑 쇼츠 {duration}초 대본을 JSON으로 작성해.
스타일: 슈피겐코리아 공식채널처럼 빠른컷+큰노란자막. 후킹: {hook_style}
제품: {product_name} / 가격: {price} / 특징: {features} / 타겟: {target}
keyword는 5~8자 한국어. narration은 자연스러운 구어체.
마크다운없이 JSON만:
{{"title":"제목25자","description":"설명","tags":["태그1","태그2","태그3","태그4","태그5"],"scenes":[{{"time":"0-3초","type":"후킹","narration":"나레이션","keyword":"핵심5~8자"}},{{"time":"3-8초","type":"문제제기","narration":"나레이션","keyword":"핵심"}},{{"time":"8-20초","type":"제품소개","narration":"나레이션","keyword":"핵심"}},{{"time":"20-28초","type":"사회적증거","narration":"나레이션","keyword":"핵심"}},{{"time":"28-{duration}초","type":"CTA","narration":"나레이션","keyword":"핵심"}}],"seo_keywords":["키워드1","키워드2","키워드3"],"thumbnail_text":"썸네일"}}"""
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text
        text = text.replace("```json", "").replace("```", "").strip()
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"Claude API 오류: {e}")
    return None

def get_sample_script(product_name, price, features, duration):
    """API 없을 때 샘플 대본"""
    return {
        "title": f"{product_name} 솔직 리뷰",
        "description": f"{product_name} 리뷰\\n{price}에 이 성능?\\n#쇼핑 #리뷰",
        "tags": ["리뷰", "추천", "가성비", "쇼츠", product_name.split()[0]],
        "scenes": [
            {"time": "0-3초", "type": "후킹", "narration": f"이 가격에 이 성능이요? {product_name} 보세요", "keyword": "가격 충격"},
            {"time": "3-8초", "type": "문제제기", "narration": f"비싼 제품 대신 {price}이면 충분합니다", "keyword": price or "가성비"},
            {"time": "8-20초", "type": "제품소개", "narration": f"핵심 기능 알려드릴게요. {features[:50]}", "keyword": "핵심 기능"},
            {"time": "20-28초", "type": "사회적증거", "narration": "별점 4.5점에 리뷰 수백 개. 써본 사람들이 인정했습니다", "keyword": "리뷰 폭발"},
            {"time": f"28-{duration}초", "type": "CTA", "narration": "링크는 댓글에 있어요. 이 가격이면 안 살 이유가 없습니다", "keyword": "지금 구매"},
        ],
        "seo_keywords": ["리뷰", "추천", "가성비"],
        "thumbnail_text": f"{price} 실화?"
    }
