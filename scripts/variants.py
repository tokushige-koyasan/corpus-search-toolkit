#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
variants.py — 異綴りマトリクス（正規表現）生成

IAST表記の検索語から、写本・電子テキストで頻出する綴り揺れを許容する
正規表現を機械生成する。9コーパス横断検索の標準手順の第1段。

段階（--tier、既定=1）:
  tier 1（既定・安全）:
    - 母音の長短揺れ: a/ā, i/ī, u/ū
    - 鼻音表記の揺れ: ṃ と同器官鼻音（ṅ ñ ṇ n m）の互換
    - 重子音/単子音の揺れ: 語中の子音（有気は kh 等を1単位として）{1,2}
  tier 2（tier1 に追加）:
    - b/v 交替（写本・ベンガル系）
    - ś/ṣ/s の交替
    - ṛ/ri の交替
  tier 3 は機械生成しない（パーリ⇄サンスクリット語形対応・鼻音消失等は
  語ごとの判断が必要なため、READMEの対応表を参照して手動で別語形を併記）

出力: 既定は正規表現1本（大文字小文字は呼び出し側で無視指定を推奨）。
--list で有限展開の列挙も出す（記録用・爆発時は打ち切り表示）。

使用例:
  python3 scripts/variants.py vajiriya
  python3 scripts/variants.py "saṃgraha" --tier 2
"""
import argparse, itertools, re, sys

# IASTトークン（長い綴りから貪欲に切る）
DIGRAPHS = ['ai','au','kh','gh','ch','jh','ṭh','ḍh','th','dh','ph','bh']
SINGLES = list('aāiīuūeoṛṝḷḹkgṅcjñṭḍṇtdnpbmyrlvśṣshṃṁḥ') + ['ḻ']

VOWEL_ALT = {'a':'[aā]','ā':'[aā]','i':'[iī]','ī':'[iī]','u':'[uū]','ū':'[uū]'}
NASALS = set('ṃṁṅñṇnm')
GEMINABLE = set(['k','g','c','j','ṭ','ḍ','t','d','p','b','m','n','ṇ','ñ','l','s','y','v','r']
                + ['kh','gh','ch','jh','ṭh','ḍh','th','dh','ph','bh'])

def tokenize(w):
    toks, i = [], 0
    while i < len(w):
        for d in DIGRAPHS:
            if w.startswith(d, i):
                toks.append(d); i += len(d); break
        else:
            toks.append(w[i]); i += 1
    return toks

def build_regex(word, tier=1):
    toks = tokenize(word.lower())
    # 前処理: 同一子音の連続（重子音）を1トークンに畳む（C C → C[dup]）
    merged = []
    for t in toks:
        if merged and merged[-1][0] == t and t in GEMINABLE:
            merged[-1] = (t, True)
        elif merged and t in ('h',) :
            merged.append((t, False))
        else:
            merged.append((t, False))
    # パーリ型 CCh（ṭṭh 等）= C + Ch の並びも畳む: C + Ch → Ch[dup]
    merged2 = []
    for t, dup in merged:
        if merged2 and len(t) == 2 and t[1] == 'h' and merged2[-1][0] == t[0]:
            merged2.pop()
            merged2.append((t, True))
        else:
            merged2.append((t, dup))

    n = len(merged2)
    parts = []
    for idx, (t, dup) in enumerate(merged2):
        last = (idx == n - 1)
        nxt = merged2[idx+1][0] if not last else None
        if t in VOWEL_ALT:
            parts.append(VOWEL_ALT[t]); continue
        if t in NASALS:
            # 子音前・語末の鼻音は表記互換クラス
            if last or (nxt and nxt not in VOWEL_ALT and nxt not in 'aāiīuūeo'):
                parts.append('[ṃṁṅñṇnm]'); continue
        if tier >= 2 and t in ('b','v'):
            core = '[bv]'
        elif tier >= 2 and t in ('ś','ṣ','s'):
            core = '[śṣs]'
        elif tier >= 2 and t == 'ṛ':
            parts.append('(?:ṛ|r[iī])'); continue
        else:
            core = t if len(t) == 1 else f'(?:{t})'
        # 重子音揺れ: 語中の可重子音は {1,2}（有気は前置の同器官無気も許容）
        if t in GEMINABLE and 0 < idx < n - 1:
            if len(t) == 2:  # 有気: ṭh → (?:ṭ?ṭh)
                parts.append(f'(?:{t[0]}?{t})')
            else:
                parts.append(f'{core}{{1,2}}')
        else:
            parts.append(core)
    return ''.join(parts)

def enumerate_variants(rx, limit=64):
    # 記録用の有限展開（クラス・量指定子を展開）
    frags = [['']]
    i = 0
    out = ['']
    tokens = re.findall(r'\[[^\]]+\]|\(\?:[^)]+\)|.\{1,2\}|.', rx)
    for tk in tokens:
        if tk.startswith('['):
            opts = list(tk[1:-1])
        elif tk.startswith('(?:') :
            body = tk[3:-1]
            opts = body.split('|') if '|' in body else [body.replace('?','')] + ([body[1:]] if body.startswith(tuple('kgcjṭḍtdpb')) and '?' in body else [])
            if '?' in body and '|' not in body:
                opts = [body.replace('?',''), body[body.index('?')+1:]]
        elif tk.endswith('{1,2}'):
            c = tk[0]; opts = [c, c+c]
        else:
            opts = [tk]
        out = [a+b for a in out for b in opts]
        if len(out) > limit:
            return out[:limit], True
    return out, False

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('word')
    ap.add_argument('--tier', type=int, default=1, choices=[1,2])
    ap.add_argument('--list', action='store_true', help='有限展開の列挙も表示')
    a = ap.parse_args()
    rx = build_regex(a.word, a.tier)
    print(rx)
    if a.list:
        vs, truncated = enumerate_variants(rx)
        for v in vs: print(' ', v, file=sys.stderr)
        if truncated: print('  …(打ち切り)', file=sys.stderr)
