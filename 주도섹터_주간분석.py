"""
주도섹터 분석 | 업종(인포스탁) + 테마 통합 [기준 : 네이버 증권]
─────────────────────────────────────────────────────────────
파이프라인
  1. 종목 리스트 로드       (Excel / CSV)
  2. 업종 크롤링            → 종목-업종 매핑  (인포스탁 79개)
  3. 테마 크롤링            → 종목-테마 매핑  (265개)
  4. 주봉 급등 횟수 계산   (양봉 & 거래량 > {SURGE_VOL_MA}주MA)
  5. 업종별 / 테마별 집계
  6. 콘솔 출력 + Excel 저장 ({입력파일명}_주간분석.xlsx)

데이터 소스
  - 업종 / 테마 매핑 : 네이버파이낸스 크롤링
  - 주봉 OHLCV      : 네이버 fchart API

한계
  - 급등 판단이 단순 기준(양봉 + 거래량 돌파)이므로 주도섹터 "셋업 확산" 확인 불가
  - 급등 기준은 김대현 Insight. Not 장호준 式 DIY
"""

import os
import re
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ════════════════════════════════════════════════════════════
# 설정
# ════════════════════════════════════════════════════════════
STOCK_LIST_FILE  = r"g:\내 드라이브\3_주식\DIY\주도섹터\26.05_11-15.xlsx"
STOCK_LIST_SHEET = 0     # 0 = 첫 번째 시트
SURGE_YEARS      = 4     # 급등 분석 기간 (년)
SURGE_VOL_MA     = 10    # 거래량 기준 이동평균 (주)

HTTP_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer":         "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 업종·테마 목록 페이지 URL이 서로 다름
_GROUP_LIST_URL = {
    'upjong': lambda p: f"https://finance.naver.com/sise/sise_group.naver?type=upjong&page={p}",
    'theme':  lambda p: f"https://finance.naver.com/sise/theme.naver?page={p}",
}


# ════════════════════════════════════════════════════════════
# 유틸: HTTP 요청
# ════════════════════════════════════════════════════════════
def _fetch(url: str):
    """GET 후 BeautifulSoup 반환. 실패 시 None."""
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10)
        resp.encoding = 'euc-kr'
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"  [오류] {url}: {e}")
        return None


# ════════════════════════════════════════════════════════════
# 1. 종목 리스트 로드
# ════════════════════════════════════════════════════════════
def load_stock_list(filepath: str):
    """
    Excel / CSV → (종목명 리스트, {종목명: 6자리코드})
    필수 컬럼: 종목코드, 종목명
    """
    ext = filepath.rsplit('.', 1)[-1].lower()
    try:
        if ext in ('xlsx', 'xls'):
            df = pd.read_excel(filepath, sheet_name=STOCK_LIST_SHEET, dtype={'종목코드': str})
        else:
            df = pd.read_csv(filepath, encoding='utf-8-sig', dtype={'종목코드': str})
    except FileNotFoundError:
        raise SystemExit(f"[오류] 파일 없음: {filepath}")

    for col in ('종목코드', '종목명'):
        if col not in df.columns:
            raise SystemExit(f"[오류] 필수 컬럼 '{col}' 없음. 현재 컬럼: {list(df.columns)}")

    df['종목코드'] = df['종목코드'].str.zfill(6)
    stocks   = df['종목명'].tolist()
    code_map = dict(zip(df['종목명'], df['종목코드']))
    print(f"  {len(stocks)}개 종목 로드 완료")
    return stocks, code_map


# ════════════════════════════════════════════════════════════
# 2. 네이버파이낸스 업종 / 테마 크롤링
# ════════════════════════════════════════════════════════════
def _get_group_list(group_type: str) -> dict:
    """
    네이버파이낸스에서 업종 또는 테마 전체 목록 수집.
    반환: {그룹코드(no): 그룹명}
    """
    label  = '업종' if group_type == 'upjong' else '테마'
    groups = {}
    page   = 1

    while True:
        soup = _fetch(_GROUP_LIST_URL[group_type](page))
        if soup is None:
            break

        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if f'type={group_type}' in href and 'no=' in href:
                m = re.search(r'no=(\d+)', href)
                if m:
                    code, name = m.group(1), a.get_text(strip=True)
                    if code not in groups and name:
                        groups[code] = name
                        found += 1

        if found == 0:
            break
        page += 1
        time.sleep(0.3)

    print(f"  {len(groups)}개 {label} {'수집 완료' if groups else '수집 실패'}")
    return groups


def _get_stocks_in_group(group_type: str, group_code: str, group_name: str) -> list:
    """
    특정 업종/테마 상세 페이지에서 소속 종목 수집 (전 페이지).
    반환: [(종목명, 종목코드), ...]  — 종목코드 기준 중복 제거
    """
    results, seen_codes, page = [], set(), 1

    while True:
        url  = f"https://finance.naver.com/sise/sise_group_detail.naver?type={group_type}&no={group_code}&page={page}"
        soup = _fetch(url)
        if soup is None:
            break

        found = 0
        for a in soup.find_all('a', href=True):
            m = re.search(r'/item/main\.naver\?code=(\d+)', a['href'])
            if m:
                code = m.group(1)
                if code not in seen_codes:
                    name = a.get_text(strip=True)
                    if name:
                        results.append((name, code))
                        seen_codes.add(code)
                        found += 1

        if not soup.select_one('a.pgRR') or found == 0:
            break
        page += 1
        time.sleep(0.2)

    return results


def crawl_group_map(group_type: str):
    """
    업종 또는 테마 전체를 크롤링해 매핑 딕셔너리 3개 반환.

      stock_to_groups : {종목명: [그룹명, ...]}
      group_to_stocks : {그룹명: [종목명, ...]}
      naver_code_map  : {종목명: 종목코드}  ← 네이버 페이지 기준 코드
    """
    label = '업종' if group_type == 'upjong' else '테마'
    print(f"\n▶ [{label}] 목록 수집")
    groups = _get_group_list(group_type)

    print(f"▶ [{label}] 종목 수집")
    stock_to_groups = {}
    group_to_stocks = {}
    naver_code_map  = {}

    for i, (code, name) in enumerate(groups.items(), 1):
        print(f"  {i}/{len(groups)}  {name:<30}", end='\r')
        pairs = _get_stocks_in_group(group_type, code, name)
        group_to_stocks[name] = [s for s, _ in pairs]
        for s_name, s_code in pairs:
            grps = stock_to_groups.setdefault(s_name, [])
            if name not in grps:
                grps.append(name)
            naver_code_map.setdefault(s_name, s_code)
        time.sleep(0.3)

    print(f"\n  완료: {len(stock_to_groups)}종목 매핑")
    return stock_to_groups, group_to_stocks, naver_code_map


# ════════════════════════════════════════════════════════════
# 3. 미매핑 종목 보완
# ════════════════════════════════════════════════════════════
def _lookup_groups_from_stock_page(code: str, group_type: str, valid_groups: set) -> list:
    """
    종목 상세 페이지에서 소속 그룹 추출.
    valid_groups 필터: 페이지 내 내비게이션 링크(동일 type= 포함)가 오탐되는 것을 차단
    """
    soup = _fetch(f"https://finance.naver.com/item/main.naver?code={code}")
    if soup is None:
        return []

    found, seen_nos = [], set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if f'type={group_type}' in href and 'no=' in href:
            m = re.search(r'no=(\d+)', href)
            if m:
                no, name = m.group(1), a.get_text(strip=True)
                if no not in seen_nos and name in valid_groups:
                    found.append(name)
                    seen_nos.add(no)
    return found


def resolve_unmapped(stocks: list, code_map: dict,
                     stock_to_groups: dict, group_to_stocks: dict,
                     naver_code_map: dict, group_type: str, label: str) -> None:
    """
    크롤링 후 매핑되지 않은 종목을 두 단계로 보완 (in-place 수정).

    단계 1 — 코드 역방향 매핑 (웹 요청 없음):
      네이버 종목명과 Excel 종목명이 달라도 종목코드가 같으면 동일 종목.
      {코드: 그룹리스트} 역방향 맵으로 이름 불일치 해소.

    단계 2 — 페이지 폴백:
      코드로도 찾지 못한 종목은 종목 상세 페이지에서 그룹 링크 직접 추출.
    """
    # 단계 1: 코드 역방향 매핑
    code_to_groups = {
        c: stock_to_groups[n]
        for n, c in naver_code_map.items()
        if n in stock_to_groups
    }
    unmapped       = [s for s in stocks if s not in stock_to_groups]
    still_unmapped = []

    for stock in unmapped:
        code   = code_map.get(stock)
        groups = code_to_groups.get(code) if code else None
        if groups:
            stock_to_groups[stock] = groups
            for g in groups:
                lst = group_to_stocks.setdefault(g, [])
                if stock not in lst:
                    lst.append(stock)
        else:
            still_unmapped.append(stock)

    # 단계 2: 페이지 폴백
    if still_unmapped:
        valid_groups = set(group_to_stocks)
        print(f"  [{label}] 코드 매핑 실패 {len(still_unmapped)}개 → 개별 페이지 조회")
        for stock in still_unmapped:
            code = code_map.get(stock)
            if not code:
                continue
            groups = _lookup_groups_from_stock_page(code, group_type, valid_groups)
            if groups:
                stock_to_groups[stock] = groups
                for g in groups:
                    lst = group_to_stocks.setdefault(g, [])
                    if stock not in lst:
                        lst.append(stock)
            time.sleep(0.3)

    final_unmapped = [s for s in stocks if s not in stock_to_groups]
    if final_unmapped:
        sample = final_unmapped[:10]
        suffix = '...' if len(final_unmapped) > 10 else ''
        print(f"  [{label}] 최종 미매핑 {len(final_unmapped)}개: {sample}{suffix}")


# ════════════════════════════════════════════════════════════
# 4. 주봉 데이터 수집 + 급등 계산
# ════════════════════════════════════════════════════════════
def fetch_weekly_ohlcv(code: str) -> pd.DataFrame:
    """
    네이버 fchart API → 주봉 OHLCV DataFrame.
    컬럼: date, open, high, low, close, volume  (분석 기간 이후 데이터만)
    """
    cutoff = datetime.today() - timedelta(days=SURGE_YEARS * 365)
    url    = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=week&count=1000&requestType=0"

    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10)
    except Exception:
        return pd.DataFrame()

    records = []
    for m in re.finditer(r'<item data="(\d{8})\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|(\d+)"', resp.text):
        date = datetime.strptime(m.group(1), '%Y%m%d')
        if date < cutoff:
            continue
        records.append({
            'date': date, 'open': int(m.group(2)), 'high': int(m.group(3)),
            'low':  int(m.group(4)), 'close': int(m.group(5)), 'volume': int(m.group(6)),
        })

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values('date').reset_index(drop=True)


def count_surge_weeks(df: pd.DataFrame) -> int:
    """
    급등 주 수 카운트.
    조건: 양봉(close > open) AND 주간거래량 > {SURGE_VOL_MA}주 거래량 이동평균
    """
    if df.empty or len(df) < SURGE_VOL_MA + 1:
        return 0
    df = df.copy()
    df['vol_ma'] = df['volume'].rolling(SURGE_VOL_MA).mean()
    df['surge']  = (df['close'] > df['open']) & (df['volume'] > df['vol_ma'])
    return int(df['surge'].sum())


# ════════════════════════════════════════════════════════════
# 5. 집계 + 출력·저장 보조 함수
# ════════════════════════════════════════════════════════════
def rank_groups_by_surge(group_to_stocks: dict, target_set: set,
                         stock_surges: dict, group_col: str) -> pd.DataFrame:
    """
    그룹(업종/테마)별 급등 통계 집계.
    target_set 에 포함된 종목만 집계 (분석 대상 외 제외).
    반환: 총급등횟수 내림차순 DataFrame, 인덱스 = 순위
    """
    rows = []
    for group, members_all in group_to_stocks.items():
        members = [s for s in members_all if s in target_set]
        if not members:
            continue
        surges = [stock_surges[s] for s in members]
        rows.append({
            group_col:      group,
            '종목수':       len(members),
            '총급등횟수':   sum(surges),
            '평균급등횟수': round(np.mean(surges), 2),
            '중앙값':       round(np.median(surges), 2),
            '최대횟수':     max(surges),
        })

    if not rows:
        return pd.DataFrame()

    df = (
        pd.DataFrame(rows)
        .sort_values(['총급등횟수', '평균급등횟수'], ascending=False)
        .reset_index(drop=True)
    )
    df.index += 1
    df.index.name = '순위'
    return df


def _build_detail_df(stocks, code_map, stock_to_upjong, stock_to_theme, stock_surges) -> pd.DataFrame:
    """종목별 상세 DataFrame 생성. 컬럼 순서: 종목코드 | 종목명 | 업종 | 테마 | 급등횟수"""
    rows = [
        {
            '종목코드': code_map.get(s, ''),
            '종목명':   s,
            '업종':     ' / '.join(stock_to_upjong.get(s, [])) or '없음',
            '테마':     ' / '.join(stock_to_theme.get(s, []))  or '없음',
            '급등횟수': stock_surges.get(s, 0),
        }
        for s in stocks
    ]
    df = (
        pd.DataFrame(rows)
        .sort_values('급등횟수', ascending=False)
        .reset_index(drop=True)
    )
    df.index += 1
    df.index.name = '순위'
    return df


def _resolve_output_path(input_path: str, suffix: str = '_주간분석') -> str:
    """입력 파일명 기반 출력 경로 생성. 파일 잠금 시 타임스탬프 추가."""
    stem     = os.path.splitext(os.path.basename(input_path))[0]
    out_dir  = os.path.dirname(os.path.abspath(input_path))
    base     = os.path.join(out_dir, stem + suffix)
    out_path = base + ".xlsx"
    try:
        with open(out_path, 'a'):
            pass
    except PermissionError:
        out_path = base + f"_{datetime.now().strftime('%H%M%S')}.xlsx"
        print(f"  파일이 열려 있어 새 파일명으로 저장: {out_path}")
    return out_path


def _save_to_excel(out_path: str, upjong_rank, theme_rank, detail_df) -> None:
    """업종랭킹·테마랭킹·종목별상세 3개 시트를 Excel로 저장."""
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        if not upjong_rank.empty:
            upjong_rank.to_excel(writer, sheet_name='업종랭킹')
        if not theme_rank.empty:
            theme_rank.to_excel(writer, sheet_name='테마랭킹')
        detail_df.to_excel(writer, sheet_name='종목별상세')
    print(f"✔ 저장 완료: {out_path}")


# ════════════════════════════════════════════════════════════
# 메인 파이프라인
# ════════════════════════════════════════════════════════════
def main():
    # ── 1. 종목 리스트 로드 ───────────────────────────────────────────────────
    print(f"▶ 종목 리스트 로드: {STOCK_LIST_FILE}")
    stocks, code_map = load_stock_list(STOCK_LIST_FILE)
    target_set = set(stocks)

    # ── 2. 업종 크롤링 ────────────────────────────────────────────────────────
    stock_to_upjong, upjong_to_stocks, upjong_naver_codes = crawl_group_map('upjong')
    resolve_unmapped(stocks, code_map,
                     stock_to_upjong, upjong_to_stocks, upjong_naver_codes,
                     'upjong', '업종')

    # ── 3. 테마 크롤링 ────────────────────────────────────────────────────────
    stock_to_theme, theme_to_stocks, theme_naver_codes = crawl_group_map('theme')
    resolve_unmapped(stocks, code_map,
                     stock_to_theme, theme_to_stocks, theme_naver_codes,
                     'theme', '테마')

    # ── 4. 주봉 급등 횟수 계산 (업종·테마 집계에 공유) ───────────────────────
    print("\n▶ 급등 횟수 계산 중...")
    stock_surges = {}
    for i, stock in enumerate(stocks, 1):
        code = code_map.get(stock)
        print(f"  {i:3d}/{len(stocks)}  {stock:<20}", end='\r')
        stock_surges[stock] = count_surge_weeks(fetch_weekly_ohlcv(code)) if code else 0
        time.sleep(0.25)
    print()

    # ── 5. 집계 ──────────────────────────────────────────────────────────────
    upjong_rank = rank_groups_by_surge(upjong_to_stocks, target_set, stock_surges, '업종명')
    theme_rank  = rank_groups_by_surge(theme_to_stocks,  target_set, stock_surges, '테마명')
    detail_df   = _build_detail_df(stocks, code_map, stock_to_upjong, stock_to_theme, stock_surges)

    # ── 6. 콘솔 출력 ─────────────────────────────────────────────────────────
    cond = f"분석기간 {SURGE_YEARS}년 | 양봉 & 거래량>{SURGE_VOL_MA}주MA"
    print(f"\n{'=' * 70}\n주도섹터 분석 결과  ({cond})\n{'=' * 70}")
    print("\n[업종 랭킹]")
    print(upjong_rank.to_string() if not upjong_rank.empty else "  집계 없음")
    print("\n[테마 랭킹]")
    print(theme_rank.to_string()  if not theme_rank.empty  else "  집계 없음")

    # ── 7. Excel 저장 ─────────────────────────────────────────────────────────
    out_path = _resolve_output_path(STOCK_LIST_FILE)
    _save_to_excel(out_path, upjong_rank, theme_rank, detail_df)


if __name__ == '__main__':
    main()
