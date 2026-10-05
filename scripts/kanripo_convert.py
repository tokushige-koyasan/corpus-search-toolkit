#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kanripo_convert.py — Kanripo（mandoku形式）→ 作品単位プレーンテキスト変換器

Kanseki Repository（github.com/kanripo、1文献1リポジトリ）の巻ファイル
（<ID>_000.txt, <ID>_001.txt, …）を、1作品1ファイルのプレーンテキストに
まとめる。kr5-corpus v1.1.0 と同じ整形規則であり、同コーパスの取得済1,650件を
catalog.csv の commit 列のSHAで取り直して変換した結果は、1,649件がバイト単位で
一致する（残る1件 KR5i0104 は kr5-corpus 側の冒頭にBOMとメタデータ行が残って
いるための差で、本変換器はBOMを読み飛ばす。--kr5-compat を付けると再現する）。

使用例:
  # 1件（clone 済みの文献リポジトリ）
  git clone --depth 1 https://github.com/kanripo/KR1a0002
  python3 scripts/kanripo_convert.py --repo KR1a0002 --out out/

  # 親フォルダ配下の KR* をすべて（部ごとの一括変換）
  python3 scripts/kanripo_convert.py --repo-dir clones/ --out out/

  # 出力を類フォルダに分けない（out/KR1a0002.txt）
  python3 scripts/kanripo_convert.py --repo-dir clones/ --out out/ --layout flat

出力:
  out/<類>/<ID>.txt        例 out/KR1a/KR1a0002.txt（BOMなし UTF-8・LF）
  out/convert_report.tsv   変換記録（--report で場所を変更できる）

整形規則（kr5-corpus と同じ）:
  1. 巻ファイルは名前順に読み、1作品1ファイルにまとめる。
  2. 行頭が「#」の行はすべて捨てる（冒頭のメタデータ行 #+TITLE: 等のほか、
     本文の途中にある # src: … / # dating: … / #+PROPERTY: … / #…# の行も含む）。
  3. <md:…>（画像リンク）と <img:…> は除く。
  4. 行末記号「¶」を除き、物理行を連結する（字下げの全角空白は残る）。
  5. <pb:X> は【X】に変え、独立した1行にする。次の行にその頁の本文全体が入る
     （頁ごとに1行）。したがって頁をまたぐ語は、頁マーカー行で分断される。
  6. 巻ファイルごとに末尾の空白類（全角空白を含む）を除き、巻と巻を改行1つで
     つなぐ。整形後に中身が空になる巻ファイルは飛ばす。ファイル末尾は改行1つ。
     巻ファイル冒頭の空白は既定で残す（--strip-head で除く。kr5 の範囲では
     どちらでも結果は同じ）。
  7. 本文の文字は変えない。異体字の統一、外字参照（&KR0001; の形）の置換、
     Unicode 正規化はしない。規則2・3・5 に当たらない記法（pb 以外のタグ、
     「:JUAN:」行、TLS系本文の見出し「** 」など）は、そのまま本文に残る。
     残った件数は変換記録に出す。

変換記録（TSV）の列:
  id / title（最初の巻ファイルの #+TITLE）/ baseedition（#+PROPERTY: BASEEDITION の
  値。複数あれば「;」区切り）/ witness（#+PROPERTY: WITNESS）/ files（巻ファイル数）/
  files_empty（整形後に空だった巻ファイル数）/ pages（頁マーカー数）/
  han_chars（漢字数。外字参照1件を1字と数える）/ body_chars（頁マーカー行と改行を
  除いた全文字数）/ gaiji_refs（外字参照の件数）/ gaiji_kinds（その種類数）/
  pua_chars（私用領域の字数）/ compat_chars（互換漢字の字数）/
  other_tags（pb 以外の「<」の数）/ hash_lines（捨てた # 行のうち本文途中のものの数）/
  commit（.git があれば HEAD のSHA）/ path / bytes / sha256

依存: Python 3 標準ライブラリのみ。
"""
import argparse, csv, glob, hashlib, os, re, subprocess, sys

VERSION = '1.3.0'
PB = re.compile(r'<pb:([^>]*)>')
DROP_TAG = re.compile(r'<(?:md|img):[^>]*>')
GAIJI = re.compile(r'&[A-Za-z][A-Za-z0-9_-]*;')
PROP = re.compile(r'^#\+PROPERTY:\s*(\S+)\s*(.*?)\s*$')
TITLE = re.compile(r'^#\+TITLE:\s*(.*?)\s*$')
REPO_ID = re.compile(r'^KR\d[a-z]\d{4}$')


def is_han(o):
    return (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0x20000 <= o <= 0x2A6DF
            or 0x2A700 <= o <= 0x2EE5F or 0x30000 <= o <= 0x323AF
            or 0xF900 <= o <= 0xFAFF or 0x2F800 <= o <= 0x2FA1F or o == 0x3007)


def is_compat(o):
    return 0xF900 <= o <= 0xFAFF or 0x2F800 <= o <= 0x2FA1F


def is_pua(o):
    return 0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0xFFFFD or 0x100000 <= o <= 0x10FFFD


def convert_file(path, meta, kr5_compat=False):
    """巻ファイル1つを整形して文字列で返す（末尾空白の処理は呼び出し側）。"""
    enc = 'utf-8' if kr5_compat else 'utf-8-sig'
    out, cur, in_body = [], '', False
    with open(path, encoding=enc, newline='') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if line.startswith('#'):
                m = PROP.match(line)
                if m:
                    key, val = m.group(1), m.group(2)
                    if key in ('BASEEDITION', 'WITNESS') and val and val not in meta[key]:
                        meta[key].append(val)
                else:
                    m = TITLE.match(line)
                    if m and not meta['TITLE']:
                        meta['TITLE'] = m.group(1)
                if in_body:
                    meta['hash_lines'] += 1
                continue
            line = DROP_TAG.sub('', line)
            line = line.replace('¶', '')
            if line.strip():
                in_body = True
            pos = 0
            for m in PB.finditer(line):
                cur += line[pos:m.start()]
                if cur:
                    out.append(cur)
                    cur = ''
                out.append('【' + m.group(1) + '】')
                pos = m.end()
            cur += line[pos:]
    if cur:
        out.append(cur)
    return '\n'.join(out)


def convert_repo(repo, kr5_compat=False, strip_head=False):
    """文献リポジトリ1件を整形する。戻り値 (本文, 記録dict)。巻ファイルが無ければ (None, 記録)。"""
    tid = os.path.basename(os.path.normpath(repo))
    files = sorted(glob.glob(os.path.join(glob.escape(repo), tid + '_*.txt')))
    meta = {'TITLE': '', 'BASEEDITION': [], 'WITNESS': [], 'hash_lines': 0}
    parts, empty = [], 0
    for f in files:
        s = convert_file(f, meta, kr5_compat)
        s = s.strip() if strip_head else s.rstrip()
        if s:
            parts.append(s)
        else:
            empty += 1
    rec = {'id': tid, 'title': meta['TITLE'], 'baseedition': ';'.join(meta['BASEEDITION']),
           'witness': ';'.join(meta['WITNESS']), 'files': len(files), 'files_empty': empty,
           'hash_lines': meta['hash_lines']}
    if not parts:
        return None, rec
    text = '\n'.join(parts) + '\n'
    rec.update(measure(text))
    return text, rec


def measure(text):
    pages = han = body = pua = compat = other = 0
    kinds = set()
    refs = 0
    for line in text.split('\n'):
        if line.startswith('【') and line.endswith('】') and '】' not in line[1:-1]:
            pages += 1
            continue
        body += len(line)
        g = GAIJI.findall(line)
        refs += len(g)
        kinds.update(g)
        rest = GAIJI.sub('', line)
        other += rest.count('<')
        for ch in rest:
            o = ord(ch)
            if is_han(o):
                han += 1
                if is_compat(o):
                    compat += 1
            elif is_pua(o):
                pua += 1
    return {'pages': pages, 'han_chars': han + refs, 'body_chars': body, 'gaiji_refs': refs,
            'gaiji_kinds': len(kinds), 'pua_chars': pua, 'compat_chars': compat, 'other_tags': other}


def git_head(repo):
    marker = os.path.join(repo, '.git')
    if not os.path.exists(marker):
        return ''
    try:
        r = subprocess.run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ''
    except OSError:
        return ''


COLS = ['id', 'title', 'baseedition', 'witness', 'files', 'files_empty', 'pages', 'han_chars',
        'body_chars', 'gaiji_refs', 'gaiji_kinds', 'pua_chars', 'compat_chars', 'other_tags',
        'hash_lines', 'commit', 'path', 'bytes', 'sha256']


def main():
    ap = argparse.ArgumentParser(description='Kanripo（mandoku形式）→ 作品単位プレーンテキスト')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--repo', help='clone 済みの文献リポジトリ1件（フォルダ名が KR1a0002 の形）')
    g.add_argument('--repo-dir', help='文献リポジトリを並べた親フォルダ（配下の KR* をすべて変換）')
    ap.add_argument('--out', required=True, help='出力先フォルダ')
    ap.add_argument('--layout', choices=['subcat', 'flat'], default='subcat',
                    help='subcat＝out/KR1a/KR1a0002.txt（既定）／flat＝out/KR1a0002.txt')
    ap.add_argument('--report', help='変換記録TSVの出力先（既定は out/convert_report.tsv）')
    ap.add_argument('--strip-head', action='store_true', help='巻ファイル冒頭の空白も除く')
    ap.add_argument('--kr5-compat', action='store_true',
                    help='kr5-corpus v1.1.0 を完全に再現する（BOMを読み飛ばさない）')
    a = ap.parse_args()

    if a.repo:
        repos = [a.repo]
    else:
        repos = sorted(os.path.join(a.repo_dir, d) for d in os.listdir(a.repo_dir)
                       if REPO_ID.match(d) and os.path.isdir(os.path.join(a.repo_dir, d)))
    os.makedirs(a.out, exist_ok=True)
    rows, n_ok, n_empty = [], 0, 0
    for repo in repos:
        tid = os.path.basename(os.path.normpath(repo))
        if not REPO_ID.match(tid):
            print(f'skip（フォルダ名がIDの形でない）: {repo}', file=sys.stderr)
            continue
        text, rec = convert_repo(repo, a.kr5_compat, a.strip_head)
        rec['commit'] = git_head(repo)
        if text is None:
            rec.update({'path': '', 'bytes': 0, 'sha256': ''})
            n_empty += 1
        else:
            rel = os.path.join(tid[:4], tid + '.txt') if a.layout == 'subcat' else tid + '.txt'
            dst = os.path.join(a.out, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            data = text.encode('utf-8')
            with open(dst, 'wb') as fh:
                fh.write(data)
            rec.update({'path': rel.replace(os.sep, '/'), 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()})
            n_ok += 1
        rows.append(rec)
    rp = a.report or os.path.join(a.out, 'convert_report.tsv')
    with open(rp, 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, delimiter='\t', lineterminator='\n')
        w.writerow(COLS)
        for r in rows:
            w.writerow([r.get(c, '') for c in COLS])
    print(f'kanripo_convert {VERSION}: 変換 {n_ok} 件／本文なし {n_empty} 件／記録 {rp}', file=sys.stderr)


if __name__ == '__main__':
    main()
