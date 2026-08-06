#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crosssearch.py — コーパス横断検索ランナー（検索マトリクス表の機械出力）

variants.py の正規表現（または任意の正規表現・複数可）を、指定した
コーパスルート群の全テキストに適用し、調査報告に転記できる
「検索語 × コーパス」マトリクス（ファイル数・総ヒット数）をTSVで出す。
--kwic で前後文脈付きの一致一覧（KWIC）も別TSVに出力する。

使用例:
  python3 scripts/crosssearch.py \
    --pattern "v[aā]j{1,2}[iī]r{1,2}[iī]y{1,2}[aā]" --label vajiriya \
    --root pali=../pali-corpus/texts --root sarit=../sarit-corpus/texts_iast \
    --kwic hits.tsv
検索対象は各rootの配下の *.txt 全件（サブフォルダ含む）。
デーヴァナーガリー原表記の層（sarit texts/ 等）ではなく、ローマ字層
（texts_iast/ 等）を指定すること。
"""
import argparse, csv, os, re, sys, unicodedata

def iter_txt(root):
    for r, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.endswith('.txt'):
                yield os.path.join(r, f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pattern', action='append', required=True, help='正規表現（複数可）')
    ap.add_argument('--label', action='append', help='patternと同数のラベル（省略時はパターン自身）')
    ap.add_argument('--root', action='append', required=True, help='name=path 形式（複数可）')
    ap.add_argument('--kwic', help='KWIC出力先TSV（前後60字）')
    ap.add_argument('--nfc', action='store_true', help='読み込み時にNFC正規化（結合文字対策）')
    a = ap.parse_args()
    labels = a.label if a.label else a.pattern
    pats = [re.compile(p, re.IGNORECASE) for p in a.pattern]
    roots = [r.split('=', 1) for r in a.root]

    kw = None
    if a.kwic:
        kw = csv.writer(open(a.kwic, 'w', encoding='utf-8', newline=''), delimiter='\t', lineterminator='\n')
        kw.writerow(['label','corpus','file','match','pre','post'])

    # マトリクス集計
    mat = {}
    for name, path in roots:
        for lab in labels: mat[(lab, name)] = [0, 0]  # files, hits
        for fp in iter_txt(path):
            t = open(fp, encoding='utf-8', errors='replace').read()
            if a.nfc: t = unicodedata.normalize('NFC', t)
            for lab, rx in zip(labels, pats):
                ms = list(rx.finditer(t))
                if ms:
                    mat[(lab, name)][0] += 1
                    mat[(lab, name)][1] += len(ms)
                    if kw:
                        for m in ms:
                            s, e = m.span()
                            kw.writerow([lab, name, os.path.relpath(fp, path),
                                         m.group(0),
                                         t[max(0,s-60):s].replace('\n',' '),
                                         t[e:e+60].replace('\n',' ')])
    # 出力
    w = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    w.writerow(['label','corpus','files_with_hits','total_hits'])
    for (lab, name), (nf, nh) in mat.items():
        w.writerow([lab, name, nf, nh])

if __name__ == '__main__':
    main()
