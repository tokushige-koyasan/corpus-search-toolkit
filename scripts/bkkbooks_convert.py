#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bkkbooks 変換器（corpus-search-toolkit v1.2.0）

bkkbooks（Kanseki Repository 次世代版）の YAML スタンドオフ形式
（本文 YAML ＋ assets/*.markers.yaml）から、頁・段・行マーカー付きの
プレーンテキストを生成する。

入力（1リポジトリ＝1文献）：
  <ID>.manifest.yaml            書誌（title・identifiers.vol/no）・巻構成
  <ID>_NNN.yaml                 基底層本文（異体字正規化済。body.text）
  assets/<ID>_NNN.markers.yaml  基底層マーカー（substitution を含む）
  editions/T/<ID>_NNN-T.yaml    T層本文（大正蔵字体）
  editions/T/assets/<ID>_NNN-T.markers.yaml  T層マーカー

出力：
  <out>/texts_T/<ID>.txt        T層（大正蔵字体）
  <out>/texts_norm/<ID>.txt     基底層（bkkbooks の variant-fold 正規化済）
  <out>/variant-fold_restored.tsv  substitution マーカーから復元した正規化対応表
  <out>/convert_report.tsv      文献ごとの統計・整合検査
  <out>/notes/variants_<ID>.tsv 校異マーカー（CBETA由来リポジトリのみ）

本文の行構成：大正蔵の1行＝出力の1行。各行頭に【T<巻>.<頁><段><行>】を付す
（例【T77.0303a04】）。巻の境界は「## juan N (<ID>_NNN)」行、ファイル冒頭は
「# 」で始まる書誌行。マーカーの content（句読点・訓点仮名・全角空白の字下げ等）は
その位置に挿入する。割注（voice/note、xml-element note）は（　）で囲む。
不可視の U+200B・U+FFFC は既定で除去する（--keep-invisible で保持）。

依存：PyYAML（標準ライブラリのみでは動かない唯一のスクリプト）。

使い方：
  python3 scripts/bkkbooks_convert.py --repo KR6t0125 --repo KR6t0126 --out kukai_C1
  python3 scripts/bkkbooks_convert.py --repo-dir bkkbooks_clones/ --out kukai_C1
"""
import argparse, glob, os, re, sys, csv, collections, hashlib, subprocess

try:
    import yaml
    _Loader = getattr(yaml, 'CSafeLoader', yaml.SafeLoader)
except ImportError:
    sys.stderr.write('PyYAML が必要です: pip install pyyaml\n')
    sys.exit(2)

VERSION = '1.2.0'
INVISIBLE = {'\u200b', '\ufffc'}
PAGE_RE = re.compile(r'(\d{4}[abc]\d{2})$')
COL_RE = re.compile(r'(\d{4}[abc])$')


def load(path):
    with open(path, encoding='utf-8') as f:
        return yaml.load(f, Loader=_Loader)


def git_head(repo):
    try:
        out = subprocess.run(['git', '-C', repo, 'log', '-1', '--format=%H %cs'],
                             capture_output=True, text=True, check=True).stdout.strip()
        return out.split()
    except Exception:
        return ['', '']


def line_id(m):
    """line-break マーカーから 頁段行ID（0303a04）を取り出す。"""
    for key in ('n', 'id'):
        v = m.get(key) or ''
        mm = PAGE_RE.search(v)
        if mm:
            return mm.group(1)
    return ''


def render(text, markers, vol, keep_invisible=False, note_stack=None):
    """1巻分の本文とマーカーからマーカー付き行リストを返す。
    返り値：(lines, stats)  lines は (page_id, text) のタプル列。"""
    # マーカーは offset 昇順・ファイル順（同一 offset ではファイル内の順序を保持）
    ms = sorted(enumerate(markers), key=lambda t: (t[1]['offset'], t[0]))
    out_lines = []
    cur = []          # 現在行のピース
    cur_id = None
    pos = 0
    n_content = 0
    open_notes = 0
    pending_close = []  # (offset) note close

    def flush():
        out_lines.append((cur_id, ''.join(cur)))

    started = False
    for _, m in ms:
        off = m['offset']
        if off > pos:
            cur.append(text[pos:off]); pos = off
        t = m['type']
        if t == 'line-break':
            if started:
                flush()
            cur = []; cur_id = line_id(m); started = True
        elif t in ('punctuation', 'indent'):
            c = m.get('content', '')
            if c in INVISIBLE and not keep_invisible:
                continue
            cur.append(c); n_content += len(c)
        elif t == 'voice' and m.get('name') == 'note':
            # 割注：offset から length 字を（　）で囲む（bkkbooks は同位置に ( ) の
            # punctuation を置くことがあるので、その場合は二重にしない）
            length = m.get('length', 0)
            seg = text[off:off + length]
            has_paren = any(x['type'] == 'punctuation' and x['offset'] == off and x.get('content') == '('
                            for x in markers)
            if not has_paren:
                cur.append('（' + seg + '）'); pos = off + length
        elif t == 'xml-element' and m.get('name') == 'note':
            if m.get('role') == 'open':
                cur.append('（'); open_notes += 1
            elif m.get('role') == 'close':
                cur.append('）')
        # substitution / page-break / paragraph-break / tls:* / list / item / p / lg / variant は無視
    if pos < len(text):
        cur.append(text[pos:])
    if started or cur:
        flush()
    return out_lines, dict(inserted=n_content, notes=open_notes)


def convert_repo(repo, out, keep_invisible=False):
    rid = os.path.basename(os.path.abspath(repo))
    man = load(os.path.join(repo, f'{rid}.manifest.yaml'))
    md = man.get('metadata', {}) or {}
    ids = md.get('identifiers', {}) or {}
    title = md.get('title') or ''
    vol = str(ids.get('vol') or '')
    no = str(ids.get('no') or '')
    # bkkbooks の一部マニフェストは vol に「2190.56」型（No.巻）を入れている
    mm = re.fullmatch(r'(\d{4}[A-Z]?)\.(\d+)', vol)
    if mm:
        no, vol = mm.group(1), mm.group(2)
    if not vol and ids.get('alt_id'):
        mm = re.match(r'T(\d+)n(\d{4}[A-Za-z]?)', ids['alt_id'][0])
        if mm:
            vol, no = mm.group(1), mm.group(2)
    sha, sha_date = git_head(repo)
    parts = sorted(man['assets']['parts'], key=lambda p: p['seq'])
    src = (md.get('source') or {}).get('repository', '')

    layers = {}
    stats = collections.OrderedDict(repo=rid, title=title, vol=vol, no=no, juans=len(parts),
                                    commit=sha, commit_date=sha_date, source=src)
    subs = collections.Counter()
    sub_entries = {}
    variants = []
    first_id = last_id = ''
    warn = []
    for layer, base_dir, suffix in (('T', os.path.join(repo, 'editions', 'T'), '-T'),
                                    ('norm', repo, '')):
        lines_all = []
        nchar = 0
        for p in parts:
            seq = p['seq']
            stem = f'{rid}_{seq:03d}'
            tp = os.path.join(base_dir, f'{stem}{suffix}.yaml')
            mp = os.path.join(base_dir, 'assets', f'{stem}{suffix}.markers.yaml')
            if not os.path.exists(tp):
                warn.append(f'{layer}: {stem} 本文なし'); continue
            d = load(tp); mk = load(mp)['markers']
            text = d['body']['text'] or ''
            front = d['front']['text'] or ''
            if not text and not front:
                lines_all.append(('juan', seq, stem, 'empty')); continue
            if front:
                fl, _ = render(front, mk.get('front', []), vol, keep_invisible)
                lines_all.append(('juan', seq, stem, 'front'))
                lines_all.extend(('line',) + l for l in fl)
            lines_all.append(('juan', seq, stem, 'body'))
            bl, st = render(text, mk.get('body', []), vol, keep_invisible)
            lines_all.extend(('line',) + l for l in bl)
            nchar += len(text)
            if layer == 'norm':
                for x in mk.get('body', []):
                    if x['type'] == 'substitution':
                        key = (x['original'], x['replacement'])
                        subs[key] += 1
                        sub_entries[key] = (x.get('mapping', {}) or {}).get('entry', '')
                    elif x['type'] == 'variant':
                        others = {k: v for k, v in x.items() if k not in ('type', 'offset', 'length', 'content', 'id')}
                        variants.append((rid, seq, x['offset'], x.get('length'), x.get('content'), others))
        layers[layer] = lines_all
        stats[f'chars_{layer}'] = nchar
        ids_seen = [l[1] for l in lines_all if l[0] == 'line' and l[1]]
        if layer == 'T':
            first_id, last_id = (ids_seen[0], ids_seen[-1]) if ids_seen else ('', '')
            stats['lines'] = sum(1 for l in lines_all if l[0] == 'line')
            stats['lines_without_id'] = sum(1 for l in lines_all if l[0] == 'line' and not l[1])
    stats['page_first'] = first_id; stats['page_last'] = last_id
    stats['layers_equal_length'] = (stats.get('chars_T') == stats.get('chars_norm'))
    stats['substitutions'] = sum(subs.values())
    stats['substitution_kinds'] = len(subs)
    stats['variants'] = len(variants)
    stats['warnings'] = '；'.join(warn)

    # 書き出し
    for layer, sub in (('T', 'texts_T'), ('norm', 'texts_norm')):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
        path = os.path.join(out, sub, f'{rid}.txt')
        layer_label = ('editions/T（大正蔵字体）' if layer == 'T' else 'bkkbooks基底層（variant-fold正規化済）')
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(f'# {rid} {title} | T{vol} No.{no} | layer: {layer_label} | '
                    f'upstream: github.com/bkkbooks/{rid}@{sha[:7]} ({sha_date}) | bkkbooks_convert.py v{VERSION}\n')
            for l in layers[layer]:
                if l[0] == 'juan':
                    tag = {'body': '', 'front': ' front', 'empty': ' 本文なし（bkkbooks側で空）'}[l[3]]
                    f.write(f'## juan {l[1]} ({l[2]}{tag})\n')
                else:
                    pid = f'【T{vol}.{l[1]}】' if l[1] else '【T%s.—】' % vol
                    f.write(pid + l[2] + '\n')
        stats[f'sha256_{layer}'] = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    if variants:
        os.makedirs(os.path.join(out, 'notes'), exist_ok=True)
        with open(os.path.join(out, 'notes', f'variants_{rid}.tsv'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('repo\tseq\toffset\tlength\tT本文\t他版本の読み\n')
            for v in variants:
                f.write('\t'.join(str(x) for x in v[:5]) + '\t' + '；'.join(f'{k}={val}' for k, val in v[5].items()) + '\n')
    return stats, subs, sub_entries


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', action='append', default=[], help='bkkbooks リポジトリのディレクトリ（複数可）')
    ap.add_argument('--repo-dir', help='配下の KR* ディレクトリをすべて対象にする')
    ap.add_argument('--out', required=True)
    ap.add_argument('--keep-invisible', action='store_true', help='U+200B・U+FFFC を保持する')
    a = ap.parse_args()
    repos = list(a.repo)
    if a.repo_dir:
        repos += sorted(d for d in glob.glob(os.path.join(a.repo_dir, 'KR*')) if os.path.isdir(d))
    if not repos:
        ap.error('--repo か --repo-dir を指定')
    os.makedirs(a.out, exist_ok=True)
    all_stats = []; all_subs = collections.Counter(); entries = {}
    per_repo_subs = collections.defaultdict(collections.Counter)
    for r in repos:
        st, subs, ents = convert_repo(r, a.out, a.keep_invisible)
        all_stats.append(st); all_subs.update(subs); entries.update(ents)
        for k, v in subs.items():
            per_repo_subs[k][st['repo']] += v
        sys.stderr.write(f"{st['repo']}\t{st['title']}\tT{st['vol']} No.{st['no']}\tjuans={st['juans']}\tlines={st['lines']}\t"
                         f"chars={st['chars_T']}\tequal={st['layers_equal_length']}\tsubs={st['substitutions']}\t{st['warnings']}\n")
    with open(os.path.join(a.out, 'convert_report.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(list(all_stats[0].keys()))
        for st in all_stats:
            w.writerow(list(st.values()))
    with open(os.path.join(a.out, 'variant-fold_restored.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('T字体（original）\t正規化（replacement）\tU+（original）\tU+（replacement）\tentry\t出現数\t出現リポジトリ\n')
        for (o, rpl), n in sorted(all_subs.items(), key=lambda t: (-t[1], t[0])):
            f.write(f"{o}\t{rpl}\t{ord(o):04X}\t{ord(rpl):04X}\t{entries.get((o, rpl), '')}\t{n}\t"
                    + ' '.join(f'{k}:{v}' for k, v in sorted(per_repo_subs[(o, rpl)].items())) + '\n')


if __name__ == '__main__':
    main()
