#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stable_match.py — テキスト間の重複・別版関係を機械判定する。

用途:
  手持ちテキストと公開コーパスの照合（完全一致／別版・類似／独自の3段階）、
  同一文献の別入力・別校訂の検出。

方法:
  1) 正規化: NFD分解→ラテン小文字以外を除去→z→s→長母音(aa等)・重子音の圧縮。
     転写方式の違い（IAST/Velthuis/Kyoto-Harvard等）を吸収するための破壊的正規化であり、
     この層は照合専用（引用・校勘には使わない）。
  2) 全文一致: 正規化文字列のMD5比較。
  3) 類似度: 正規化文字列のk字接片（既定k=16）をCRC32の剰余で安定サンプリングし、
     含有率 contain(A→B) = |A標本 ∩ B接片| / |A標本| を計る。
     ※Python組込みhash()はプロセスごとにシードが変わるため照合には使えない。
     本スクリプトはCRC32使用のため、別プロセス・別日の実行結果同士でも比較可能。
  4) 冒頭・末尾: 正規化文字列の先頭・末尾150字のdifflib類似度を併記する。

判定の目安（既定閾値、--th-* で変更可）:
  完全一致          norm_md5一致、または contain≥0.9 かつ 冒頭・末尾≥0.85
  別版・類似        contain≥0.25、または contain≥0.15 かつ 冒頭/末尾いずれか≥0.5
  独自              上記に達しない

使い方:
  python3 scripts/stable_match.py --query 手持ち.txt --targets コーパス/texts/
  python3 scripts/stable_match.py --query 手持ちdir/ --targets root1/ root2/ --top 3
出力はTSV（query, verdict, target, contain, head_sim, tail_sim）。
"""
import argparse, hashlib, os, re, sys, unicodedata, zlib
from difflib import SequenceMatcher

def norm(s):
    s = unicodedata.normalize('NFD', s).lower()
    s = ''.join(c for c in s if 'a' <= c <= 'z')
    s = s.replace('z', 's')
    s = re.sub(r'([aiu])\1+', r'\1', s)
    return re.sub(r'(.)\1+', r'\1', s)

def read_norm(path):
    raw = open(path, 'rb').read()
    for enc in ('utf-8', 'utf-16', 'latin-1'):
        try:
            return norm(raw.decode(enc))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return norm(raw.decode('latin-1', 'replace'))

def grams(n, k, mod):
    out = set()
    for i in range(len(n) - k):
        g = n[i:i+k]
        if zlib.crc32(g.encode()) % mod == 0:
            out.add(g)
    return out

def files_in(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for dp, _, fns in os.walk(p):
                if '.git' in dp:
                    continue
                for fn in sorted(fns):
                    yield os.path.join(dp, fn)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--query', required=True, help='照合したいファイルまたはディレクトリ')
    ap.add_argument('--targets', required=True, nargs='+', help='照合先root（複数可）')
    ap.add_argument('-k', type=int, default=16)
    ap.add_argument('--mod', type=int, default=61)
    ap.add_argument('--top', type=int, default=3)
    ap.add_argument('--th-contain', type=float, default=0.25)
    ap.add_argument('--th-weak', type=float, default=0.15)
    ap.add_argument('--th-exact', type=float, default=0.9)
    a = ap.parse_args()

    tgt = []
    for p in files_in(a.targets):
        n = read_norm(p)
        if len(n) < a.k + 1:
            continue
        tgt.append((p, hashlib.md5(n.encode()).hexdigest(),
                    grams(n, a.k, a.mod), n[:150], n[-150:]))
    print(f'targets indexed: {len(tgt)}', file=sys.stderr)

    print('query\tverdict\ttarget\tcontain\thead_sim\ttail_sim')
    for q in files_in([a.query]):
        n = read_norm(q)
        if len(n) < a.k + 1:
            print(f'{q}\t対象外（短小）\t\t\t\t')
            continue
        qmd5 = hashlib.md5(n.encode()).hexdigest()
        qg = grams(n, a.k, a.mod)
        scored = []
        for p, md5, g, h, t in tgt:
            if md5 == qmd5:
                scored.append((p, 1.0, 1.0, 1.0, True))
                continue
            c = len(qg & g) / max(len(qg), 1)
            if c >= a.th_weak * 0.6:
                hs = SequenceMatcher(None, n[:150], h).ratio()
                ts = SequenceMatcher(None, n[-150:], t).ratio()
                scored.append((p, c, hs, ts, False))
        scored.sort(key=lambda x: -x[1])
        if not scored:
            print(f'{q}\t独自\t\t\t\t')
            continue
        best = scored[0]
        if best[4] or (best[1] >= a.th_exact and best[2] >= 0.85 and best[3] >= 0.85):
            verdict = '完全一致'
        elif best[1] >= a.th_contain or (best[1] >= a.th_weak and max(best[2], best[3]) >= 0.5):
            verdict = '別版・類似'
        else:
            verdict = '独自'
        for p, c, hs, ts, ex in scored[:a.top]:
            print(f'{q}\t{verdict}\t{p}\t{c:.3f}\t{hs:.2f}\t{ts:.2f}')
            verdict = ''

if __name__ == '__main__':
    main()
