#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""to_iast.py — 非IAST転写のテキストをIASTに機械変換する。

対応方式:
  velthuis    ASCII転写（aa/.t/;s 等）→ IAST
  at          @記法（X@ でダイアクリティクス付加: a@=ā, s@=ṣ, j@=ñ, c@=ś 等）→ IAST
  mac-norman  旧Mac系フォント写像（Norman系8ビット）→ IAST
  auto        内容から上記を推定（既定）

設計方針:
  - 原文ファイルは変更しない（出力は別ファイル/別ディレクトリ）。
  - 変換はすべて機械的な字面置換であり、sandhi再解釈・校訂は行わない。
  - 英語書誌行（Edition/Input等の語を含みマーカーを含まない行）は変換しない。
  - 変換できない字はU+FFFDにせず〔xx〕(16進)で本文中に明示し、件数を報告する。
  - 出力はBOMなしUTF-8・LF・NFC。

使い方:
  python3 scripts/to_iast.py IN.txt -o OUT.txt
  python3 scripts/to_iast.py --scheme velthuis --strip-tex IN.tex -o OUT.txt
  python3 scripts/to_iast.py --indir SRC/ --outdir DEST/        # ディレクトリ一括
残存数などの報告はstderrにTSVで出す（file, scheme, residual_markers, residual_undef）。
"""
import argparse, os, re, sys, unicodedata

VEL = [('aa','ā'),('ii','ī'),('uu','ū'),('.r.r','ṝ'),('.rr','ṝ'),('.r','ṛ'),
       ('.ll','ḹ'),('.l','ḷ'),('.t','ṭ'),('.d','ḍ'),('.n','ṇ'),('.s','ṣ'),
       ('.m','ṃ'),('.h','ḥ'),('.g','ṅ'),('"s','ś'),(';s','ś'),('"n','ṅ'),
       (';n','ñ'),('~n','ñ'),(':n','ṅ'),('~m','ṃ')]

AT = {'a':'ā','i':'ī','u':'ū','r':'ṛ','t':'ṭ','d':'ḍ','n':'ṇ','s':'ṣ','m':'ṃ',
      'h':'ḥ','j':'ñ','c':'ś','g':'ṅ','l':'ḷ'}
AT.update({k.upper():v.upper() for k,v in AT.items()})

# 旧Mac系（Norman系）8ビット写像。実文書の文脈照合から復元した表。
MAC = {0x8c:'ā',0x8e:'é',0x91:'ū',0x95:'ï',0x96:'ñ',0x9c:'ū',0x9f:'ü',
       0xa0:'ṭ',0xa1:'†',0xa5:'ṝ',0xa7:'ś',0xa8:'ṛ',0xb4:'ī',0xb5:'ṃ',
       0xb6:'ḍ',0xb7:'ṣ',0xba:'ṅ',0xd5:'’',0xe8:'ū',0xea:'Ś',0xee:'Ā',
       0xf6:'ṇ',0xfa:'ḥ'}

ENG = re.compile(r'\b(the|and|of|by|edition|edited|input|copyright|version|'
                 r'based|press|university|chapter|source|file|text)\b', re.I)
MARK = re.compile(r'[.;"~:][rtdnsmhlg]')

def strip_tex(t):
    t = re.sub(r'(?m)%.*$', '', t)
    t = re.sub(r'\\(begin|end)\{[^}]*\}', ' ', t)
    t = re.sub(r'\\[A-Za-z]+(\[[^\]]*\])?', '', t)
    t = re.sub(r'[{}]', '', t)
    return re.sub(r'\n{3,}', '\n\n', t)

def conv_velthuis(t):
    out = []
    for line in t.split('\n'):
        if ENG.search(line) and not MARK.search(line):
            out.append(line); continue
        s = line
        for a, b in VEL:
            s = s.replace(a, b)
        out.append(s)
    return '\n'.join(out)

def conv_at(t):
    return re.sub(r'([A-Za-z])@', lambda m: AT.get(m.group(1), m.group(0)), t)

def conv_mac(raw):
    out = []; undef = 0
    for x in raw:
        if x < 0x80:
            out.append(chr(x))
        elif x in MAC:
            out.append(MAC[x])
        else:
            out.append(f'〔{x:02x}〕'); undef += 1
    return ''.join(out), undef

def detect(raw, text):
    if raw is not None and any(x >= 0x80 for x in raw):
        try:
            raw.decode('utf-8'); 
        except UnicodeDecodeError:
            return 'mac-norman'
    if len(re.findall(r'[A-Za-z]@', text)) > 50:
        return 'at'
    if MARK.search(text) or re.search(r'aa|ii|uu', text):
        return 'velthuis'
    return 'none'

def convert_file(path, scheme, striptex):
    raw = open(path, 'rb').read()
    undef = 0
    text = None
    if scheme == 'mac-norman':
        t, undef = conv_mac(raw)
        t = unicodedata.normalize('NFC', t).replace('\r\n','\n').replace('\r','\n')
        return t, 'mac-norman', 0, undef
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        # 非UTF-8: 日本語系（cp932）かMac系かを判別する
        try:
            cand = raw.decode('cp932')
            if any('\u3000' <= c <= '\u9fff' for c in cand):
                text = cand          # 日本語注記入りテキスト → 通常処理へ
        except UnicodeDecodeError:
            pass
        if text is None:
            if scheme == 'auto':
                t, undef = conv_mac(raw)
                t = unicodedata.normalize('NFC', t).replace('\r\n','\n').replace('\r','\n')
                return t, 'mac-norman', 0, undef
            text = raw.decode('utf-8', 'replace')
    text = unicodedata.normalize('NFC', text).replace('\r\n','\n').replace('\r','\n')
    if striptex or text.lstrip().startswith('\\documentclass'):
        text = strip_tex(text)
    s = detect(None, text) if scheme == 'auto' else scheme
    if s == 'velthuis':
        text = conv_velthuis(text)
    elif s == 'at':
        text = conv_at(text)
    marks = len(MARK.findall(text))
    return text, s, marks, undef

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('infile', nargs='?')
    ap.add_argument('-o', '--out')
    ap.add_argument('--indir'); ap.add_argument('--outdir')
    ap.add_argument('--scheme', default='auto',
                    choices=['auto','velthuis','at','mac-norman'])
    ap.add_argument('--strip-tex', action='store_true')
    a = ap.parse_args()
    jobs = []
    if a.indir:
        os.makedirs(a.outdir, exist_ok=True)
        for fn in sorted(os.listdir(a.indir)):
            p = os.path.join(a.indir, fn)
            if os.path.isfile(p):
                jobs.append((p, os.path.join(a.outdir, os.path.splitext(fn)[0]+'.txt')))
    else:
        jobs.append((a.infile, a.out or os.path.splitext(a.infile)[0]+'_iast.txt'))
    print('file\tscheme\tresidual_markers\tresidual_undef', file=sys.stderr)
    for src, dst in jobs:
        t, s, marks, undef = convert_file(src, a.scheme, a.strip_tex)
        with open(dst, 'w', encoding='utf-8', newline='\n') as f:
            f.write(t)
        print(f'{src}\t{s}\t{marks}\t{undef}', file=sys.stderr)

if __name__ == '__main__':
    main()
