"""
주도섹터 분석
- 네이버파이낸스 테마 페이지에서 종목-테마 매핑 크롤링
- 분석 대상 종목의 급등 횟수(양봉 + 주간거래량 > 주간10MA)를 테마별로 집계
- 분석기간: 4년
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime, timedelta
import numpy as np

# ── 분석 대상 종목 리스트 ────────────────────────────────────────────────────
TARGET_STOCKS = """두산
DL
기아
가온전선
SK하이닉스
영풍
현대건설
한화
DB하이텍
CJ
유진투자증권
GS글로벌
상상인증권
PKC
KG케미칼
세아베스틸지주
대한전선
현대차증권
SK증권
SK네트웍스
한양증권
오리온홀딩스
삼화콘덴서
코오롱
SYTS
고려제강
KCC
HS화성
진흥기업
삼영무역
TYM
코오롱글로벌
디아이
일신방직
유화증권
유안타증권
한화투자증권
대신증권
LG
KG모빌리티
포스코퓨처엠
삼영
에이스침대
롯데정밀화학
신세계
한솔테크닉스
효성
한신공영
휴스틸
코스모신소재
SGC에너지
동진쎄미켐
현대차
현대지에프홀딩스
POSCO홀딩스
삼영전자
파미셀
대원산업
에스엘
대한해운
삼성전자
NH투자증권
동부건설
삼아알미늄
LS
대원전선
GS건설
삼성SDI
대한유화
미래에셋증권
보성파워텍
GS리테일
DN오토모티브
이수페타시스
코리아써키트
대덕
삼성전기
SIMPAC
삼화전기
포스코엠텍
한화솔루션
명신산업
OCI홀딩스
LS ELECTRIC
삼성중공업
대한광통신
화신
퍼스텍
LG이노텍
롯데케미칼
현대위아
서한
한농화성
세보엠이씨
와이투솔루션
한신기계
금호석유화학
DB
현대모비스
더존비즈온
경인양행
하이록코리아
아진산업
화승코퍼레이션
디와이
계룡건설
성광벤드
한솔케미칼
대창단조
성우하이텍
일진홀딩스
삼성증권
DB증권
두올
세명전기
수산세보틱스
SK텔레콤
현대엘리베이터
한국알콜
한온시스템
베뉴지
와이지-원
한섬
롯데에너지머티리얼즈
에이티넘인베스트
KCC건설
포스코DX
태광
롯데쇼핑
인지컨트롤스
유성티엔에스
한국단자
이구산업
남해화학
동화기업
아주IB투자
BGF
팜스토리
삼성E&A
동아지질
삼성물산
HLB
팬오션
케이씨
다올투자증권
교보증권
에스에이엠티
신세계인터내셔날
신세계푸드
피에스케이홀딩스
케이엠더블유
삼성생명
제룡전기
엠케이전자
자화전자
네패스
KT&G
피노
두산에너빌리티
SK
한국기업평가
아비코전자
에이치엠넥스
금화피에스시
유니셈
SFA반도체
NC
팜스코
나이스정보통신
에프에스티
솔브레인홀딩스
진성티이씨
주성엔지니어링
파워넷
파세코
성도이엔지
삼지전자
이오테크닉스
에스티아이
키움증권
다산네트웍스
나노엔텍
누리플렉스
아이씨디
현대에버다임
코미팜
비츠로테크
링네트
새로닉스
한미반도체
성호전자
피에이치에이
KSS해운
한양이엔지
오르비텍
서울반도체
우원개발
대우건설
포스코인터내셔널
파워로직스
코데즈컴바인
인탑스
코메론
쎌바이오텍
쏠리드
인터플렉스
에스티큐브
코텍
한전기술
아모텍
아이앤씨
케이엔솔
금강철강
프로텍
한미글로벌
이랜텍
아이디스홀딩스
한컴위드
신한지주
에스에프에이
코위버
현대홈쇼핑
포스코스틸리온
리노공업
에스피지
미코
아진엑스텍
LS마린솔루션
LB세미콘
산일전기
인텍플러스
현대로템
티씨케이
케이프
에프앤가이드
이루온
큐에스아이
LG전자
엘앤에프
하나마이크론
세이브존I&C
현대백화점
한국금융지주
LIG아큐버
우리손에프앤지
원익QnC
해성옵틱스
덕산하이메탈
STX엔진
LS증권
유비쿼스홀딩스
HB테크놀러지
메디포스트
한양디지텍
대주전자재료
가온그룹
GS
제우스
LIG디펜스앤에어로스
전진건설로봇
동양이엔피
제주반도체
오킨스전자
일진다이아
쎄크
한화엔진
비츠로셀
엘오티베큠
GST
에프엔에스테크
휴온스글로벌
유진테크
헬릭스미스
뉴프렉스
네오티스
현대글로비스
유니테스트
동국제약
에코프로
비엠티
하나금융지주
동아엘텍
쏘닉스
테크윙
THE E&M
HDC현대EP
코세스
브이엠
상아프론테크
비에이치
상신이디피
디엔에프
서울바이오시스
KPX홀딩스
한라IMS
엑시콘
LF
빅솔론
후성
매커스
동운아나텍
일진파워
슈프리마에이치큐
웨이브일렉트로
ISC
테스
대창솔루션
SK이노베이션
HJ중공업
마이크로컨텍솔
고영
뷰웍스
머큐리
미래에셋벤처투자
월덱스
어보브반도체
이엔에프테크놀로지
코오롱생명과학
일진전기
티케이케미칼""".strip().split('\n')

TARGET_STOCKS = [s.strip() for s in TARGET_STOCKS]

# 티커-종목명 매핑 (제공된 데이터 기반) ─────────────────────────────────────
STOCK_CODE_MAP = {
    "두산": "000150", "DL": "000210", "기아": "000270", "가온전선": "000500",
    "SK하이닉스": "000660", "영풍": "000670", "현대건설": "000720", "한화": "000880",
    "DB하이텍": "000990", "CJ": "001040", "유진투자증권": "001200", "GS글로벌": "001250",
    "상상인증권": "001290", "PKC": "001340", "KG케미칼": "001390", "세아베스틸지주": "001430",
    "대한전선": "001440", "현대차증권": "001500", "SK증권": "001510", "SK네트웍스": "001740",
    "한양증권": "001750", "오리온홀딩스": "001800", "삼화콘덴서": "001820", "코오롱": "002020",
    "SYTS": "002170", "고려제강": "002240", "KCC": "002380", "HS화성": "002460",
    "진흥기업": "002780", "삼영무역": "002810", "TYM": "002900", "코오롱글로벌": "003070",
    "디아이": "003160", "일신방직": "003200", "유화증권": "003460", "유안타증권": "003470",
    "한화투자증권": "003530", "대신증권": "003540", "LG": "003550", "KG모빌리티": "003620",
    "포스코퓨처엠": "003670", "삼영": "003720", "에이스침대": "003800", "롯데정밀화학": "004000",
    "신세계": "004170", "한솔테크닉스": "004710", "효성": "004800", "한신공영": "004960",
    "휴스틸": "005010", "코스모신소재": "005070", "SGC에너지": "005090", "동진쎄미켐": "005290",
    "현대차": "005380", "현대지에프홀딩스": "005440", "POSCO홀딩스": "005490", "삼영전자": "005680",
    "파미셀": "005690", "대원산업": "005710", "에스엘": "005850", "대한해운": "005880",
    "삼성전자": "005930", "NH투자증권": "005940", "동부건설": "005960", "삼아알미늄": "006110",
    "LS": "006260", "대원전선": "006340", "GS건설": "006360", "삼성SDI": "006400",
    "대한유화": "006650", "미래에셋증권": "006800", "보성파워텍": "006910", "GS리테일": "007070",
    "DN오토모티브": "007340", "이수페타시스": "007660", "코리아써키트": "007810", "대덕": "008060",
    "삼성전기": "009150", "SIMPAC": "009160", "삼화전기": "009470", "포스코엠텍": "009520",
    "한화솔루션": "009830", "명신산업": "009900", "OCI홀딩스": "010060", "LS ELECTRIC": "010120",
    "삼성중공업": "010140", "대한광통신": "010170", "화신": "010690", "퍼스텍": "010820",
    "LG이노텍": "011070", "롯데케미칼": "011170", "현대위아": "011210", "서한": "011370",
    "한농화성": "011500", "세보엠이씨": "011560", "와이투솔루션": "011690", "한신기계": "011700",
    "금호석유화학": "011780", "DB": "012030", "현대모비스": "012330", "더존비즈온": "012510",
    "경인양행": "012610", "하이록코리아": "013030", "아진산업": "013310", "화승코퍼레이션": "013520",
    "디와이": "013570", "계룡건설": "013580", "성광벤드": "014620", "한솔케미칼": "014680",
    "대창단조": "015230", "성우하이텍": "015750", "일진홀딩스": "015860", "삼성증권": "016360",
    "DB증권": "016610", "두올": "016740", "세명전기": "017510", "수산세보틱스": "017550",
    "SK텔레콤": "017670", "현대엘리베이터": "017800", "한국알콜": "017890", "한온시스템": "018880",
    "베뉴지": "019010", "와이지-원": "019210", "한섬": "020000", "롯데에너지머티리얼즈": "020150",
    "에이티넘인베스트": "021080", "KCC건설": "021320", "포스코DX": "022100", "태광": "023160",
    "롯데쇼핑": "023530", "인지컨트롤스": "023800", "유성티엔에스": "024800", "한국단자": "025540",
    "이구산업": "025820", "남해화학": "025860", "동화기업": "025900", "아주IB투자": "027360",
    "BGF": "027410", "팜스토리": "027710", "삼성E&A": "028050", "동아지질": "028100",
    "삼성물산": "028260", "HLB": "028300", "팬오션": "028670", "케이씨": "029460",
    "다올투자증권": "030210", "교보증권": "030610", "에스에이엠티": "031330", "신세계인터내셔날": "031430",
    "신세계푸드": "031440", "피에스케이홀딩스": "031980", "케이엠더블유": "032500", "삼성생명": "032830",
    "제룡전기": "033100", "엠케이전자": "033160", "자화전자": "033240", "네패스": "033640",
    "KT&G": "033780", "피노": "033790", "두산에너빌리티": "034020", "SK": "034730",
    "한국기업평가": "034950", "아비코전자": "036010", "에이치엠넥스": "036170", "금화피에스시": "036190",
    "유니셈": "036200", "SFA반도체": "036540", "NC": "036570", "팜스코": "036580",
    "나이스정보통신": "036800", "에프에스티": "036810", "솔브레인홀딩스": "036830", "진성티이씨": "036890",
    "주성엔지니어링": "036930", "파워넷": "037030", "파세코": "037070", "성도이엔지": "037350",
    "삼지전자": "037460", "이오테크닉스": "039030", "에스티아이": "039440", "키움증권": "039490",
    "다산네트웍스": "039560", "나노엔텍": "039860", "누리플렉스": "040160", "아이씨디": "040910",
    "현대에버다임": "041440", "코미팜": "041960", "비츠로테크": "042370", "링네트": "042500",
    "새로닉스": "042600", "한미반도체": "042700", "성호전자": "043260", "피에이치에이": "043370",
    "KSS해운": "044450", "한양이엔지": "045100", "오르비텍": "046120", "서울반도체": "046890",
    "우원개발": "046940", "대우건설": "047040", "포스코인터내셔널": "047050", "파워로직스": "047310",
    "코데즈컴바인": "047770", "인탑스": "049070", "코메론": "049430", "쎌바이오텍": "049960",
    "쏠리드": "050890", "인터플렉스": "051370", "에스티큐브": "052020", "코텍": "052330",
    "한전기술": "052690", "아모텍": "052710", "아이앤씨": "052860", "케이엔솔": "053080",
    "금강철강": "053260", "프로텍": "053610", "한미글로벌": "053690", "이랜텍": "054210",
    "아이디스홀딩스": "054800", "한컴위드": "054920", "신한지주": "055550", "에스에프에이": "056190",
    "코위버": "056360", "현대홈쇼핑": "057050", "포스코스틸리온": "058430", "리노공업": "058470",
    "에스피지": "058610", "미코": "059090", "아진엑스텍": "059120", "LS마린솔루션": "060370",
    "LB세미콘": "061970", "산일전기": "062040", "인텍플러스": "064290", "현대로템": "064350",
    "티씨케이": "064760", "케이프": "064820", "에프앤가이드": "064850", "이루온": "065440",
    "큐에스아이": "066310", "LG전자": "066570", "엘앤에프": "066970", "하나마이크론": "067310",
    "세이브존I&C": "067830", "현대백화점": "069960", "한국금융지주": "071050", "LIG아큐버": "073490",
    "우리손에프앤지": "073560", "원익QnC": "074600", "해성옵틱스": "076610", "덕산하이메탈": "077360",
    "STX엔진": "077970", "LS증권": "078020", "유비쿼스홀딩스": "078070", "HB테크놀러지": "078150",
    "메디포스트": "078160", "한양디지텍": "078350", "대주전자재료": "078600", "가온그룹": "078890",
    "GS": "078930", "제우스": "079370", "LIG디펜스앤에어로스": "079550", "전진건설로봇": "079900",
    "동양이엔피": "079960", "제주반도체": "080220", "오킨스전자": "080580", "일진다이아": "081000",
    "쎄크": "081180", "한화엔진": "082740", "비츠로셀": "082920", "엘오티베큠": "083310",
    "GST": "083450", "에프엔에스테크": "083500", "휴온스글로벌": "084110", "유진테크": "084370",
    "헬릭스미스": "084990", "뉴프렉스": "085670", "네오티스": "085910", "현대글로비스": "086280",
    "유니테스트": "086390", "동국제약": "086450", "에코프로": "086520", "비엠티": "086670",
    "하나금융지주": "086790", "동아엘텍": "088130", "쏘닉스": "088280", "테크윙": "089030",
    "THE E&M": "089230", "HDC현대EP": "089470", "코세스": "089890", "브이엠": "089970",
    "상아프론테크": "089980", "비에이치": "090460", "상신이디피": "091580", "디엔에프": "092070",
    "서울바이오시스": "092190", "KPX홀딩스": "092230", "한라IMS": "092460", "엑시콘": "092870",
    "LF": "093050", "빅솔론": "093190", "후성": "093370", "매커스": "093520",
    "동운아나텍": "094170", "일진파워": "094820", "슈프리마에이치큐": "094840", "웨이브일렉트로": "095270",
    "ISC": "095340", "테스": "095610", "대창솔루션": "096350", "SK이노베이션": "096770",
    "HJ중공업": "097230", "마이크로컨텍솔": "098120", "고영": "098460", "뷰웍스": "100120",
    "머큐리": "100590", "미래에셋벤처투자": "100790", "월덱스": "101160", "어보브반도체": "102120",
    "이엔에프테크놀로지": "102710", "코오롱생명과학": "102940", "일진전기": "103590", "티케이케미칼": "104480",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# ── 1. 네이버파이낸스 테마 크롤링 ────────────────────────────────────────────
def get_theme_list():
    """
    네이버파이낸스 테마 목록 수집.
    실제 링크 패턴: /sise/sise_group_detail.naver?type=theme&no=155
    → no= 파라미터 사용 (themeCode= 아님)
    """
    themes = {}  # theme_code -> theme_name
    page = 1
    while True:
        url = f"https://finance.naver.com/sise/theme.naver?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = 'euc-kr'
        except Exception as e:
            print(f"  [오류] 테마 목록 페이지 {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        found = 0
        # 실제 패턴: href="/sise/sise_group_detail.naver?type=theme&no=155"
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'type=theme' in href and 'no=' in href:
                m = re.search(r'no=(\d+)', href)
                if m:
                    code = m.group(1)
                    name = a.get_text(strip=True)
                    if code not in themes and name:
                        themes[code] = name
                        found += 1

        if found == 0:
            break
        page += 1
        time.sleep(0.3)

    print(f"  총 {len(themes)}개 테마 수집 완료")
    return themes


def get_stocks_in_theme(theme_code, theme_name):
    """
    특정 테마의 종목 목록과 종목코드 수집.
    종목 링크 패턴: /item/main.naver?code=005930
    returns: list of (종목명, 종목코드)
    """
    results = []  # (name, code) tuples
    page = 1
    while True:
        url = (
            f"https://finance.naver.com/sise/sise_group_detail.naver"
            f"?type=theme&no={theme_code}&page={page}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = 'euc-kr'
        except Exception as e:
            print(f"  [오류] 테마 {theme_name} p{page}: {e}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        found = 0
        # 종목 링크만 선택: /item/main.naver?code= 패턴
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/item/main.naver' in href and 'code=' in href:
                m = re.search(r'code=(\d+)', href)
                if m:
                    stock_name = a.get_text(strip=True)
                    stock_code = m.group(1)
                    if stock_name:
                        results.append((stock_name, stock_code))
                        found += 1

        next_page = soup.select_one('a.pgRR')
        if not next_page or found == 0:
            break
        page += 1
        time.sleep(0.2)

    return results


def build_stock_theme_map():
    """
    종목 → 테마 리스트 매핑 + 종목명 → 종목코드 매핑 구성.
    테마 크롤링 시 종목코드도 함께 추출하여 별도 검색 불필요.
    """
    print("▶ 테마 목록 수집 중...")
    themes = get_theme_list()

    print("▶ 각 테마별 종목 수집 중...")
    stock_to_themes = {}   # 종목명 -> [테마명, ...]
    stock_to_code   = {}   # 종목명 -> 종목코드
    theme_stocks_map = {}  # 테마명 -> [종목명, ...]

    for i, (code, name) in enumerate(themes.items(), 1):
        print(f"  [{i}/{len(themes)}] {name}          ", end='\r')
        stock_pairs = get_stocks_in_theme(code, name)
        stock_names = [s for s, _ in stock_pairs]
        theme_stocks_map[name] = stock_names
        for s_name, s_code in stock_pairs:
            stock_to_themes.setdefault(s_name, []).append(name)
            if s_name not in stock_to_code:
                stock_to_code[s_name] = s_code
        time.sleep(0.3)

    print(f"\n  종목-테마 매핑 완료: {len(stock_to_themes)}종목")
    return stock_to_themes, theme_stocks_map, stock_to_code


# ── 3. 주가 데이터 조회 및 급등 횟수 계산 ────────────────────────────────────
def fetch_weekly_data(code, years=4):
    """
    네이버파이낸스 fchart API로 주봉 데이터 수집.
    URL: fchart.stock.naver.com/sise.nhn?symbol=...&timeframe=week
    응답 형식(XML): <item data="날짜|시가|고가|저가|종가|거래량" />
    (sise_week.naver는 폐지됨 → fchart API 사용)
    """
    count = years * 52 + 10  # 4년 ≈ 208주, 여유분 포함
    url = (
        f"https://fchart.stock.naver.com/sise.nhn"
        f"?symbol={code}&timeframe=week&count={count}&requestType=0"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = 'euc-kr'
    except Exception:
        return pd.DataFrame()

    cutoff = datetime.today() - timedelta(days=years * 365)
    records = []

    # XML을 regex로 파싱 (lxml 의존성 없이 안정적으로 처리)
    for m in re.finditer(r'data="([^"]+)"', resp.text):
        parts = m.group(1).split('|')
        if len(parts) < 6:
            continue
        try:
            date    = datetime.strptime(parts[0], '%Y%m%d')
            open_p  = int(parts[1])
            high_p  = int(parts[2])
            low_p   = int(parts[3])
            close_p = int(parts[4])
            volume  = int(parts[5])
        except Exception:
            continue
        if date < cutoff:
            continue
        records.append({
            'date': date, 'open': open_p, 'high': high_p,
            'low': low_p, 'close': close_p, 'volume': volume,
        })

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records).sort_values('date').reset_index(drop=True)


def count_surges(df, ma_period=10):
    """
    급등 조건: 양봉(close > open) AND 주간거래량 > 주간 거래량 10MA
    반환: 급등 주 수
    """
    if df.empty or len(df) < ma_period + 1:
        return 0

    df = df.copy()
    df['vol_ma'] = df['volume'].rolling(ma_period).mean()
    df['bullish'] = df['close'] > df['open']
    df['surge']   = df['bullish'] & (df['volume'] > df['vol_ma'])
    return int(df['surge'].sum())


# ── 4. 종목코드로 개별 페이지에서 테마 조회 (미매핑 종목용) ──────────────────
def get_themes_by_code(code):
    """
    종목 상세 페이지에서 소속 테마 링크 추출.
    테마 링크 패턴: /sise/sise_group_detail.naver?type=theme&no=XXX
    """
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')
        themes = []
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'type=theme' in href and 'no=' in href:
                name = a.get_text(strip=True)
                if name and name not in seen:
                    themes.append(name)
                    seen.add(name)
        return themes
    except Exception:
        return []


# ── 5. 전체 파이프라인 ────────────────────────────────────────────────────────
def main():
    # Step 1: 테마-종목 매핑 크롤링
    stock_to_themes, theme_stocks_map, _ = build_stock_theme_map()

    # Step 2: 미매핑 종목 → 개별 페이지로 테마 추가 조회
    unmapped = [s for s in TARGET_STOCKS if s not in stock_to_themes]
    if unmapped:
        print(f"\n⚠  1차 매핑 실패 {len(unmapped)}개 → 개별 페이지 재조회 중...")
        for s in unmapped:
            code = STOCK_CODE_MAP.get(s)
            if not code:
                continue
            themes = get_themes_by_code(code)
            if themes:
                stock_to_themes[s] = themes
                for t in themes:
                    theme_stocks_map.setdefault(t, [])
                    if s not in theme_stocks_map[t]:
                        theme_stocks_map[t].append(s)
                print(f"  ✔ {s}: {themes}")
            time.sleep(0.3)

    still_unmapped = [s for s in TARGET_STOCKS if s not in stock_to_themes]
    if still_unmapped:
        print(f"\n  최종 테마 없음 ({len(still_unmapped)}개): {still_unmapped}")

    # Step 3: 전체 320종목 급등 횟수 계산 (STOCK_CODE_MAP 사용)
    print("\n▶ 전체 종목 급등 횟수 계산 중...")
    stock_surges = {}
    total = len(TARGET_STOCKS)
    for i, stock in enumerate(TARGET_STOCKS, 1):
        code = STOCK_CODE_MAP.get(stock)
        print(f"  [{i:3d}/{total}] {stock:<20}", end='\r')
        if not code:
            stock_surges[stock] = 0
            continue
        df = fetch_weekly_data(code, years=4)
        stock_surges[stock] = count_surges(df)
        time.sleep(0.25)
    print()

    # Step 4: 테마별 집계
    print("▶ 테마별 집계 중...")
    target_set = set(TARGET_STOCKS)
    theme_stats = []

    for theme_name, theme_stocks in theme_stocks_map.items():
        members = [s for s in theme_stocks if s in target_set]
        if not members:
            continue
        surges = [stock_surges.get(s, 0) for s in members]
        theme_stats.append({
            '테마명':         theme_name,
            '종목수':         len(members),
            '총급등횟수':     sum(surges),
            '평균급등횟수':   round(np.mean(surges), 2),
            '중앙값급등횟수': round(np.median(surges), 2),
            '최대횟수':       max(surges),
        })

    if not theme_stats:
        print("⚠  집계 결과가 없습니다.")
        return

    result = (
        pd.DataFrame(theme_stats)
        .sort_values(['총급등횟수', '평균급등횟수'], ascending=False)
        .reset_index(drop=True)
    )
    result.index += 1
    result.index.name = '순위'

    # Step 5: 출력 & 저장
    print("\n" + "=" * 75)
    print("주도섹터 분석 결과 (분석기간: 4년 | 급등조건: 양봉 & 주간거래량>10MA)")
    print("=" * 75)
    print(result.to_string())

    base_path = r"g:\내 드라이브\3_주식\DIY\주도섹터\주도섹터_결과_v2"
    out_path = base_path + ".xlsx"
    # 파일이 열려 있으면 타임스탬프 붙인 이름으로 저장
    try:
        open(out_path, 'a').close()
    except PermissionError:
        out_path = base_path + f"_{datetime.now().strftime('%H%M%S')}.xlsx"
        print(f"  기존 파일이 열려 있어 새 파일로 저장: {out_path}")
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        result.to_excel(writer, sheet_name='테마랭킹')

        # 종목별상세 시트 (전 320종목 포함)
        detail_rows = []
        for stock in TARGET_STOCKS:
            themes = stock_to_themes.get(stock, [])
            detail_rows.append({
                '종목코드': STOCK_CODE_MAP.get(stock, ''),
                '종목명':   stock,
                '테마':     ' / '.join(themes) if themes else '테마없음',
                '급등횟수': stock_surges.get(stock, 0),
            })
        detail_df = (
            pd.DataFrame(detail_rows)
            .sort_values('급등횟수', ascending=False)
            .reset_index(drop=True)
        )
        detail_df.index += 1
        detail_df.to_excel(writer, sheet_name='종목별상세')

    print(f"\n✔ 결과 저장 완료: {out_path}")


if __name__ == '__main__':
    main()
