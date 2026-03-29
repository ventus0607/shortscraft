"""
대본 생성 엔진 - Claude API 또는 샘플
"""
import json

def generate_with_claude(product_name, price, features, target, hook_style, duration, api_key):
    """Claude API로 대본 생성"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""유튜브 쇼핑 쇼츠 대본을 JSON으로 만들어줘.

규칙:
- 실제 유튜버처럼 자연스러운 구어체 ("~거든요", "~잖아요", "솔직히", "진짜")
- keyword는 5~8자 짧은 핵심 단어 (자막용)
- 슈피겐코리아 공식 쇼츠 스타일 참고
- 각 장면에 time 필드 포함 (예: "0:00~0:05")

제품: {product_name}
가격: {price or "미정"}
특징: {features}
타겟: {target}
길이: {duration}초
후킹: {hook_style}

JSON만 출력 (코드블록 없이):
{{"title":"제목","scenes":[{{"type":"후킹","time":"0:00~0:05","narration":"나레이션","keyword":"자막키워드","duration":5}},{{"type":"문제제기","time":"0:05~0:10","narration":"나레이션","keyword":"키워드","duration":5}},{{"type":"제품소개","time":"0:10~0:20","narration":"나레이션","keyword":"키워드","duration":10}},{{"type":"사회적증거","time":"0:20~0:25","narration":"나레이션","keyword":"키워드","duration":5}},{{"type":"CTA","time":"0:25~0:30","narration":"나레이션","keyword":"키워드","duration":5}}],"description":"설명란 텍스트","tags":["태그1","태그2","태그3","태그4","태그5"],"seo_keywords":["키워드1","키워드2","키워드3"],"hooks_alt":["대체후킹1","대체후킹2"]}}"""

        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system="You are a JSON API. Output ONLY valid JSON. No markdown, no explanation, no code fences.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw = msg.content[0].text
        # Parse JSON with fallbacks
        return _parse_json(raw)
    except Exception as e:
        print(f"Claude API error: {e}")
        return None

def _parse_json(raw):
    """JSON 파싱 (여러 전략)"""
    if not raw:
        return None
    txt = raw
    import re
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', txt)
    if fence:
        txt = fence.group(1)
    i = txt.find("{")
    j = txt.rfind("}")
    if i < 0 or j < 0:
        return None
    s = txt[i:j+1]
    try:
        return json.loads(s)
    except:
        s = re.sub(r',\s*([}\]])', r'\1', s)
        try:
            return json.loads(s)
        except:
            return None

def get_sample_script(product_name, price, features, duration):
    """샘플 대본 (API 키 없을 때)"""
    feat_list = [f.strip() for f in features.split(",") if f.strip()]
    feat1 = feat_list[0] if len(feat_list) > 0 else "최고 성능"
    feat2 = feat_list[1] if len(feat_list) > 1 else "가성비"
    feat3 = feat_list[2] if len(feat_list) > 2 else "편리함"
    
    return {
        "title": f"{product_name} 써보고 놀란 이유",
        "scenes": [
            {
                "type": "후킹",
                "time": "0:00~0:05",
                "narration": f"솔직히 {price or '이 가격'}에 이 성능이요? 진짜 실화냐고요",
                "keyword": "이 가격 실화?",
                "duration": 5
            },
            {
                "type": "문제제기",
                "time": "0:05~0:10",
                "narration": f"비싼 거 사자니 부담되고, 싼 거 사자니 불안하잖아요",
                "keyword": "고민 끝!",
                "duration": 5
            },
            {
                "type": "제품소개",
                "time": f"0:10~0:{10 + duration//3}",
                "narration": f"{product_name} 직접 써봤는데요, {feat1}에 {feat2}까지 진짜 미쳤거든요",
                "keyword": feat1[:7],
                "duration": duration // 3
            },
            {
                "type": "사회적증거",
                "time": f"0:{10 + duration//3}~0:{duration - 5}",
                "narration": f"리뷰 보면 다들 {feat3} 때문에 재구매한다고 하더라고요",
                "keyword": "후기 폭발",
                "duration": duration // 3
            },
            {
                "type": "CTA",
                "time": f"0:{duration - 5}~0:{duration}",
                "narration": f"링크 타고 가면 {price or '할인가'}에 살 수 있어요. 진짜 이건 찐이에요",
                "keyword": "지금 구매!",
                "duration": 5
            }
        ],
        "description": f"""🔥 {product_name} 리뷰

✅ {feat1}
✅ {feat2}  
✅ {feat3}

👇 최저가 구매 링크
[쿠팡 파트너스 링크]

이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.

#쇼츠 #{product_name.replace(' ','')} #가성비 #추천 #쿠팡""",
        "tags": [product_name.split()[0], "가성비", "추천", "리뷰", "쿠팡"],
        "seo_keywords": [product_name, f"{product_name} 리뷰", f"{product_name} 추천"],
        "hooks_alt": [
            f"이거 안 쓰면 손해예요 진짜로",
            f"{product_name} 왜 이제야 알았을까"
        ]
    }
