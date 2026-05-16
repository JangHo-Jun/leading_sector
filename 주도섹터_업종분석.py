"""
주도섹터 분석
- 네이버파이낸스 인포스탁섹터(키움증권 API) 페이지에서 종목-섹터 매핑 크롤링
- 분석 대상 종목의 급등 횟수(양봉 + 주간거래량 > 주간10MA)를 섹터별로 집계
- 분석기간: 4년
- 종목 리스트 / 티커 매핑: 종목리스트.csv (또는 .xlsx) 파일로 관리
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime, timedelta
import numpy as np

# ── 설정 ─────────────────────────────────────────────────────────────────────
STOCK_LIST_FILE  = r"g:\내 드라이브\3_주식\DIY\주도섹터\26.05_11-15.xlsx"
STOCK_LIST_SHEET = 0      # 0=첫 번째 시트, 특정 시트는 예: '종목별'

# Naver Finance 분류 유형 (sise_group.naver?type= 파라미터):
#   "upjong" → 인포스탁섹터 / GICS 업종 (79개, 키움증권 기반) ← 기본값
#   "theme"  → 네이버 자체 테마 (265개)
#   "group"  → 기업집단/그룹 (62개)
THEME_TYPE  = "upjong"
THEME_LABEL = {"upjong": "업종(인포스탁)", "theme": "테마", "group": "기업집단"}.get(THEME_TYPE, THEME_TYPE)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# ── 0. 종목 리스트 로드 ────────────────────────────────────────────────────────
def load_stock_list(filepath):
    """CSV 또는 Excel 파일에서 종목 리스트와 티커 매핑 로드.
    파일 컬럼: 종목코드(6자리), 종목명
    """
    try:
        ext = filepath.rsplit('.', 1)[-1].lower()
        if ext in ('xlsx', 'xls'):
            df = pd.read_excel(filepath, sheet_name=STOCK_LIST_SHEET, dtype={'종목코드': str})
        else:
            df = pd.read_csv(filepath, encoding='utf-8-sig', dtype={'종목코드': str})
    except FileNotFoundError:
        raise SystemExit(f"[오류] 종목 리스트 파일을 찾을 수 없습니다: {filepath}")
    for col in ('종목코드', '종목명'):
        if col not in df.columns:
            raise SystemExit(f"[오류] 필수 컬럼 '{col}' 없음. 현재 컬럼: {list(df.columns)}")
    df['종목코드'] = df['종목코드'].str.zfill(6)
    target_stocks = df['종목명'].tolist()
    stock_code_map = dict(zip(df['종목명'], df['종목코드']))
    print(f"  {len(target_stocks)}개 종목 로드 완료")
    return target_stocks, stock_code_map


# ── 1. 네이버파이낸스 인포스탁섹터 크롤링 ────────────────────────────────────
def get_theme_list():
    """
    네이버파이낸스 인포스탁섹터(또는 테마) 목록 수집.
    링크 패턴: /sise/sise_group_detail.naver?type={THEME_TYPE}&no=XXX
    """
    themes = {}
    page = 1
    while True:
        url = f"https://finance.naver.com/sise/sise_group.naver?type={THEME_TYPE}&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = 'euc-kr'
        except Exception as e:
            print(f"  [오류] 섹터 목록 페이지 {page}: {e}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if f'type={THEME_TYPE}' in href and 'no=' in href:
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

    if not themes:
        print(f"  ⚠ 섹터 0개 수집 — THEME_TYPE('{THEME_TYPE}') 또는 URL이 올바르지 않을 수 있습니다.")
        print(f"    브라우저로 확인: https://finance.naver.com/sise/sise_group.naver?type={THEME_TYPE}&page=1")
    else:
        print(f"  총 {len(themes)}개 섹터 수집 완료")
    return themes


def get_stocks_in_theme(theme_code, theme_name):
    """
    특정 섹터의 종목 목록과 종목코드 수집.
    종목 링크 패턴: /item/main.naver?code=005930
    returns: list of (종목명, 종목코드)
    """
    results = []
    seen_codes = set()  # 전체 페이지에 걸쳐 중복 제거
    page = 1
    while True:
        url = (
            f"https://finance.naver.com/sise/sise_group_detail.naver"
            f"?type={THEME_TYPE}&no={theme_code}&page={page}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = 'euc-kr'
        except Exception as e:
            print(f"  [오류] 섹터 {theme_name} p{page}: {e}")
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/item/main.naver' in href and 'code=' in href:
                m = re.search(r'code=(\d+)', href)
                if m:
                    stock_code = m.group(1)
                    if stock_code not in seen_codes:
                        stock_name = a.get_text(strip=True)
                        if stock_name:
                            results.append((stock_name, stock_code))
                            seen_codes.add(stock_code)
                            found += 1

        next_page = soup.select_one('a.pgRR')
        if not next_page or found == 0:
            break
        page += 1
        time.sleep(0.2)

    return results


def build_stock_theme_map():
    """종목 → 섹터 리스트 매핑 + 종목명 → 종목코드 매핑 구성."""
    print("▶ 섹터 목록 수집 중...")
    themes = get_theme_list()

    print("▶ 각 섹터별 종목 수집 중...")
    stock_to_themes  = {}
    stock_to_code    = {}
    theme_stocks_map = {}

    for i, (code, name) in enumerate(themes.items(), 1):
        print(f"  [{i}/{len(themes)}] {name}          ", end='\r')
        stock_pairs = get_stocks_in_theme(code, name)
        stock_names = [s for s, _ in stock_pairs]
        theme_stocks_map[name] = stock_names
        for s_name, s_code in stock_pairs:
            sectors = stock_to_themes.setdefault(s_name, [])
            if name not in sectors:  # 같은 섹터명 중복 추가 방지
                sectors.append(name)
            if s_name not in stock_to_code:
                stock_to_code[s_name] = s_code
        time.sleep(0.3)

    print(f"\n  종목-섹터 매핑 완료: {len(stock_to_themes)}종목")
    return stock_to_themes, theme_stocks_map, stock_to_code


# ── 2. 주봉 데이터 수집 (네이버 fchart API) ──────────────────────────────────
def fetch_weekly_data(code, years=4):
    """네이버 fchart API로 주봉 OHLCV 수집."""
    cutoff = datetime.today() - timedelta(days=years * 365)
    url = (
        f"https://fchart.stock.naver.com/sise.nhn"
        f"?symbol={code}&timeframe=week&count=1000&requestType=0"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
    except Exception:
        return pd.DataFrame()

    records = []
    for m in re.finditer(
        r'<item data="(\d{8})\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|(\d+)"', resp.text
    ):
        date = datetime.strptime(m.group(1), '%Y%m%d')
        if date < cutoff:
            continue
        records.append({
            'date':   date,
            'open':   int(m.group(2)),
            'high':   int(m.group(3)),
            'low':    int(m.group(4)),
            'close':  int(m.group(5)),
            'volume': int(m.group(6)),
        })

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values('date').reset_index(drop=True)


def count_surges(df, ma_period=10):
    """급등 조건: 양봉(close > open) AND 주간거래량 > 주간 거래량 10MA"""
    if df.empty or len(df) < ma_period + 1:
        return 0

    df = df.copy()
    df['vol_ma'] = df['volume'].rolling(ma_period).mean()
    df['bullish'] = df['close'] > df['open']
    df['surge']   = df['bullish'] & (df['volume'] > df['vol_ma'])
    return int(df['surge'].sum())


# ── 3. 종목코드로 개별 페이지에서 섹터 조회 (미매핑 종목용) ─────────────────
def get_themes_by_code(code, valid_sectors):
    """종목 상세 페이지에서 소속 업종 추출 (최종 폴백 — 코드 매핑 실패 시에만 사용).

    valid_sectors: set of sector names from main crawl — 내비게이션 링크 차단용.
    """
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')
        themes = []
        seen_nos = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            if f'type={THEME_TYPE}' in href and 'no=' in href:
                m = re.search(r'no=(\d+)', href)
                if m:
                    no = m.group(1)
                    if no not in seen_nos:
                        name = a.get_text(strip=True)
                        if name and name in valid_sectors:
                            themes.append(name)
                            seen_nos.add(no)
        return themes
    except Exception:
        return []


# ── 4. 전체 파이프라인 ────────────────────────────────────────────────────────
def main():
    # Step 0: 종목 리스트 로드
    print(f"▶ 종목 리스트 로드 중: {STOCK_LIST_FILE}")
    TARGET_STOCKS, STOCK_CODE_MAP = load_stock_list(STOCK_LIST_FILE)

    # Step 1: 섹터-종목 매핑 크롤링
    stock_to_themes, theme_stocks_map, stock_to_code = build_stock_theme_map()

    # Step 2a: 종목코드 역방향 맵으로 이름 불일치 해소 (웹 요청 없이)
    code_to_sectors = {code: stock_to_themes[name]
                       for name, code in stock_to_code.items()
                       if name in stock_to_themes}

    unmapped = [s for s in TARGET_STOCKS if s not in stock_to_themes]
    still_unmapped = []
    for s in unmapped:
        code = STOCK_CODE_MAP.get(s)
        sectors = code_to_sectors.get(code) if code else None
        if sectors:
            stock_to_themes[s] = sectors
            for t in sectors:
                if s not in theme_stocks_map.setdefault(t, []):
                    theme_stocks_map[t].append(s)
        else:
            still_unmapped.append(s)

    # Step 2b: 코드로도 못 찾은 종목만 개별 페이지 폴백
    if still_unmapped:
        valid_sectors = set(theme_stocks_map.keys())
        print(f"\n⚠  코드 매핑 실패 {len(still_unmapped)}개 → 개별 페이지 재조회 중...")
        for s in still_unmapped:
            code = STOCK_CODE_MAP.get(s)
            if not code:
                continue
            themes = get_themes_by_code(code, valid_sectors)
            if themes:
                stock_to_themes[s] = themes
                for t in themes:
                    if s not in theme_stocks_map.setdefault(t, []):
                        theme_stocks_map[t].append(s)
                print(f"  ✔ {s}: {themes}")
            time.sleep(0.3)

    final_unmapped = [s for s in TARGET_STOCKS if s not in stock_to_themes]
    if final_unmapped:
        print(f"\n  최종 섹터 없음 ({len(final_unmapped)}개): {final_unmapped}")

    # Step 3: 전체 종목 급등 횟수 계산
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

    # Step 4: 섹터별 집계
    print("▶ 섹터별 집계 중...")
    target_set = set(TARGET_STOCKS)
    theme_stats = []

    for theme_name, theme_stocks in theme_stocks_map.items():
        members = [s for s in theme_stocks if s in target_set]
        if not members:
            continue
        surges = [stock_surges.get(s, 0) for s in members]
        theme_stats.append({
            '섹터명':         theme_name,
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
    print(f"주도섹터 분석 결과 (분석기간: 4년 | 급등조건: 양봉 & 주간거래량>10MA | 섹터: {THEME_LABEL})")
    print("=" * 75)
    print(result.to_string())

    base_path = r"g:\내 드라이브\3_주식\DIY\주도섹터\주도섹터_결과_v3"
    out_path = base_path + ".xlsx"
    try:
        with open(out_path, 'a'):
            pass
    except PermissionError:
        out_path = base_path + f"_{datetime.now().strftime('%H%M%S')}.xlsx"
        print(f"  기존 파일이 열려 있어 새 파일로 저장: {out_path}")

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        result.to_excel(writer, sheet_name='섹터랭킹')

        detail_rows = []
        for stock in TARGET_STOCKS:
            themes = stock_to_themes.get(stock, [])
            detail_rows.append({
                '종목코드': STOCK_CODE_MAP.get(stock, ''),
                '종목명':   stock,
                '섹터':     ' / '.join(themes) if themes else '섹터없음',
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
