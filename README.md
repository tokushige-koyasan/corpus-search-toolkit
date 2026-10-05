# corpus-search-toolkit

宗教文献・漢籍コーパス群（pali・kanseki・kr1・kr5・gretil・sarit・dcs・muktabodha・84000-tm・cdsl ほか）の横断検索における綴り揺れ対策の標準手順とツール、および取り込み用の変換器（Kanripo・bkkbooks）である。固有名詞検索で母音長短の揺れにより偽ゼロが生じた事例（vajiriya で検索し vājiriyā を取り逃す）の再発防止を目的とする。

## 標準手順（4段階）

1. **正規表現の生成**：検索語（IAST）から `scripts/variants.py` で異綴りマトリクスの正規表現を生成する。既定の tier 1 は母音長短・鼻音表記・重子音の揺れを包摂する。

   ```
   python3 scripts/variants.py vajiriya
   → v[aā]j{1,2}[iī]r{1,2}[iī]y{1,2}[aā]
   ```

2. **tier 2 の要否判断**：写本系・地域系の交替（b/v、ś/ṣ/s、ṛ/ri）まで拾う場合は `--tier 2` を付す。ヒットの偽陽性は増えるため、固有名詞や稀語で取り逃しの代償が大きい場合に用いる。

3. **別語形の手動併記（tier 3）**：パーリ⇄サンスクリット語形対応など機械生成に馴染まない揺れは、下の対応表を参照して**別の検索語として並列指定**する（例：vajra 系を追う場合は vajira 系を別パターンで併走させる）。

4. **横断検索と記録**：`scripts/crosssearch.py` にパターン（複数可）とコーパスルートを渡し、マトリクスTSV（検索語×コーパス×ファイル数・ヒット数）と KWIC 一覧を出力する。**調査報告には使用した正規表現とマトリクス表を必ず記載する**（検索式が再現可能であることが報告の検証可能性を担保する）。

   ```
   python3 scripts/crosssearch.py \
     --pattern "$(python3 scripts/variants.py vajiriya)" --label vajiriya \
     --root pali=../pali-corpus/texts \
     --root sarit=../sarit-corpus/texts_iast \
     --kwic hits.tsv > matrix.tsv
   ```

## 各コーパスの推奨検索ルート

ローマ字検索は必ずローマ字層に対して行うこと（原表記層への検索は偽ゼロの原因になる）。

| corpus | 推奨root | 注意 |
|---|---|---|
| pali | `pali-corpus/texts` | 全217件ローマ字（v1.1.0で残存デーヴァナーガリー0字） |
| sarit | `sarit-corpus/texts_iast` ＋ `texts` | texts_iast/はデーヴァナーガリー41件の機械転写層。IAST原符号化の42件はtexts/にしかないため、**両方をrootに指定**する（texts/側のデーヴァナーガリー41件にローマ字検索は当たらないだけで害はない）。典拠引用はtexts/を参照 |
| gretil | `gretil-corpus/texts` | |
| dcs | `dcs-corpus` の本文復元層 | 解析データ（CoNLL-U）ではなく本文復元側を用いる |
| muktabodha | `muktabodha-corpus/texts` | |
| 84000-tm | 対訳TSVの蔵文・英文列 | IAST検索の対象外（蔵文はワイリー） |
| cdsl | `cdsl-corpus/dicts` | 辞書はSLP1符号化の辞書があるため、IAST検索前にREADMEで符号化を確認 |
| kr1 / kr5 | `kr1-corpus/KR1a` 〜 `KR1j`、`kr5-corpus/KR5a` 〜 `KR5i`（類・部ごとに `--root KR1a=…/KR1a` の形で指定すると類別のマトリクスになる） | Kanripo型の漢文コーパス。`variants.py` は使わず、正規表現を手で書く。(1) 異体字は文字クラスで並べる（`[教敎]`）。(2) 本文は頁ごとに1行なので、頁をまたぐ語は頁マーカー行で分断される。(3) 行をまたぐ語には字下げの全角空白、割注の中の行替え「/」、割注の行またぎ「)(」が挟まる。下の「漢文コーパス（Kanripo型）の検索式」を参照 |
| kanseki | 漢文コーパス | 本手順の対象外（漢字表記の異体字問題は別途） |

## tier 3 対応表（手動併記の代表例）

パーリ⇄サンスクリットの規則的対応。左右いずれの形でも文献に現れうるため、両形を並列パターンで検索する。

| Skt | Pali | 例 |
|---|---|---|
| vajra | vajira | Vajrayāna / vajirayāna |
| ārya | ariya / ayya | |
| kṣ | kkh / cch | kṣetra / khetta, kṣaṇa / khaṇa |
| jñ | ññ | prajñā / paññā |
| ṛ | a / i / u | kṛta / kata, ṛṣi / isi, ṛju / uju |
| dharma / karma | dhamma / kamma | -rC- 全般が -CC- |
| sūtra | sutta | -tr- → -tt- |
| śr / sr | s | śrāvaka / sāvaka |
| 語頭 st / sth | th / ṭh | sthavira / thera |

その他の手動判断事項：鼻音の消失・挿入（saṃgraha / saggaha）、母音 e・o と短母音の交替（パーリ写本）、地名・人名の語末長短（-a / -ā）。

## 漢文コーパス（Kanripo型）の検索式（v1.3.0追加）

kr1-corpus・kr5-corpus（`scripts/kanripo_convert.py` の出力）は、頁マーカー【…】が独立した1行で、次の1行にその頁の本文全体が入る。底本の字体のまま収めているので、同じ語が複数の字形で現れる。漢字の異体字を同一視する機能は本ツール群に無く、検索式の側で扱う。式は次の4段階で書き、件数の差を表にして報告する。

| 式 | 内容 | 例（教育） |
|---|---|---|
| A | 素の文字列 | `教育` |
| B | 異体字を文字クラスで並べる | `[教敎]育` |
| C | B に加え、二字の間の区切り（字下げの全角空白、割注の中の行替え「/」、頁の変わり目）を許す | `[教敎](?:[　/]\|\n【[^】\n]*】\n)*育` |
| D | C に加え、割注の行またぎ「)(」を許す（標準の式） | `[教敎](?:[　/]\|\)[　]*(?:\n【[^】\n]*】\n)?[　]*\(\|\n【[^】\n]*】\n)*育` |

（表の中の `\|` は表の区切りと紛れないための表記で、実際の式は `|` である。）

```
python3 scripts/crosssearch.py \
  --pattern '[教敎](?:[　/]|\)[　]*(?:\n【[^】\n]*】\n)?[　]*\(|\n【[^】\n]*】\n)*育' --label 教育_D \
  --root KR1a=../kr1-corpus/KR1a --root KR1h=../kr1-corpus/KR1h \
  --kwic hits.tsv > matrix.tsv
```

kr1-corpus v1.0.0（経部719件）での実測（総ヒット数）:

| 語 | A | B | C | D |
|---|---:|---:|---:|---:|
| 教育 | 106 | 141 | 144 | 148 |
| 教化 | 1,611 | 1,923 | 1,979 | 1,988 |
| 教誨 | 641 | 856 | 875 | 881 |
| 教訓 | 395 | 510 | 525 | 529 |
| 教導 | 119 | 141 | 147 | 147 |
| 養育 | 270 | 287 | 297 | 303 |
| 訓育 | 6 | 6 | 6 | 6 |

注意:

- 素の文字列（A）だけでは、式Dに対して教育で約28％、教誨で約27％を取り逃す。大半は異体字（敎）による
- 割注が行をまたぐと、割注がいったん閉じて次の行で開き直すので、二字の間に「)(」が挟まる（例: `英才而教)　(育之`）。式Cはこれを拾わず、式Dが拾う。式Dは、本文から割注に入る境目（`教(育`）は拾わない
- 全角空白を区切りに入れると、空白で区切られた別々の語（表・見出し・列挙）も拾う。KWIC で確かめること
- crosssearch.py の KWIC の match 列には、一致した文字列がそのまま入る（頁またぎの一致には改行と頁マーカーを含む）。どの区切りに当たったかは match 列で分かる
- 外字は `&KR0694;` の形の参照のまま残る。語の一方が外字参照になっている場合は拾えない
- 経書の正文など一部の文献は現代の標点つきの本文である（kr1-corpus では11件。catalog.csv の review_flag 列で識別できる）

異体字の実測（kr1-corpus v1.0.0。式B・C・Dに入れた字）:

| 字 | 式に入れた字形（経部での出現数） | 入れなかった主な字（出現数・理由） |
|---|---|---|
| 教 | 教（56,104）、敎（12,090） | 斆（486）・斅（7）＝別字、學＝別字 |
| 育 | 育（10,273） | 毓（773）＝人名が大半で、対象語に当たるのは「養毓」1件。式に入れず別ラベルで数える。鬻・淯＝借字、冑＝別字、袬（4）＝字書の見出しのみ |
| 化 | 化（52,187）、㐶（2） | 𠏁（1）＝字書の見出しのみ、貨・花・匕＝別字 |
| 誨 | 誨（3,853） | 戒＝借字 |
| 訓 | 訓（29,770） | 順・馴・紃＝借字 |
| 導 | 導（10,730）、𨗳（280） | 䆃＝借字 |
| 養 | 養（51,621）、飬（3,587）、䍩（19）、羪（6） | 翔・恙・癢＝借字、眷＝別字 |

候補は Unihan の異体字データ（unicode-org/unihan-database の kSemanticVariant・kZVariant ほか）、cjkvi/cjkvi-variants、Unicode の互換漢字（NFKC で対象字に写る字）、kanripo/KR-Gaiji の正規化欄から集め、経部での出現数と用例を見て決めた。出所のデータに無い字形（𨗳）もあったので、別の語を検索するときは、相手側の字の分布（「X育」の X に来る字の一覧など）を出して字形を点検すること。互換漢字（U+F900–FAFF、U+2F800–2FA1F）は経部に19種・1,106字あるが、上の7字に写るものは出ない。

## 出力の様式

- マトリクスTSV：`label / corpus / files_with_hits / total_hits`。報告にはこの表と各labelの正規表現を対で掲げる
- KWIC TSV：`label / corpus / file / match / pre / post`（前後60字）。引用時は各コーパスの原ファイル（sarit は texts/ の原符号化）に立ち返って確認する
- ヒット0の報告には「当該正規表現・当該rootの範囲で0」という限定を付す（コーパス未収録文献の存在——Pradīpoddyotana 等——による見かけの0と区別するため）

## 依存

Python 3 標準ライブラリのみ（外部パッケージ不要）。例外は `scripts/bkkbooks_convert.py` で、PyYAML（`pip install pyyaml`）を要する。`scripts/kanripo_convert.py` は標準ライブラリのみで動き、入力フォルダが git の作業ツリーであれば変換記録に上流のコミットSHAを書く（git コマンドを呼ぶ。無ければ空欄）。

## 転写変換器（v1.1.0追加）：scripts/to_iast.py

非IAST転写のテキストをIASTへ機械変換する。私蔵e-text等をコーパス群と同じ土俵で横断検索するための前処理であり、原文は変更せず別ファイルに書き出す（引用・校勘は原文と刊本を参照）。変換は字面置換のみでsandhi再解釈は行わない。英語書誌行は変換対象から保護する。

対応方式（--scheme、既定はauto判定）：

| 方式 | 内容 | 例 |
|---|---|---|
| velthuis | ASCII転写 | aa→ā, .t→ṭ, ;s/"s→ś, ~n/;n→ñ, :n→ṅ |
| at | @記法（X@でダイアクリティクス付加） | a@→ā, s@→ṣ, j@→ñ, c@→ś |
| mac-norman | 旧Mac系フォント写像（Norman系8ビット） | 0xa7→ś, 0xb5→ṃ, 0xfa→ḥ |

```
python3 scripts/to_iast.py IN.txt -o OUT.txt
python3 scripts/to_iast.py --indir 原文dir/ --outdir iast_dir/
```

変換できない字は〔xx〕（16進）で本文中に明示し、残存数をstderrにTSVで報告する（残存フラグ付き収録の方針）。TeXマークアップは--strip-tex（\documentclass検出時は自動）でプレーン化してから変換する。出力はBOMなしUTF-8・LF・NFC。

## 重複・別版判定器（v1.1.0追加）：scripts/stable_match.py

手持ちテキストとコーパスの照合（完全一致／別版・類似／独自の3段階）、同一文献の別入力・別校訂の検出に用いる。

```
python3 scripts/stable_match.py --query 手持ち.txt --targets ../gretil-corpus/texts/
python3 scripts/stable_match.py --query 手持ちdir/ --targets root1/ root2/ --top 3
```

方法は (1) 破壊的正規化（転写方式差の吸収。照合専用で引用不可）(2) 正規化全文MD5 (3) 16字接片のCRC32安定サンプリングによる含有率 (4) 冒頭・末尾150字の類似度。判定の目安：完全一致＝MD5一致または含有率0.9以上かつ冒頭末尾0.85以上／別版・類似＝含有率0.25以上等／独自＝いずれも未達。閾値は--th-*で変更できる。

**注意**：Python組込みhash()はプロセスごとにシードが変わるため、保存した接片ハッシュを別実行と比較すると全件不一致になる（偽の「独自」判定を生む）。本スクリプトがCRC32を使うのはこのためであり、自作の照合処理でも組込みhash()を照合に使ってはならない。

## Kanripo 変換器（v1.3.0追加）：scripts/kanripo_convert.py

Kanseki Repository（github.com/kanripo、1文献1リポジトリ、mandoku形式）の巻ファイル（`<ID>_000.txt`, `<ID>_001.txt`, …）を、1作品1ファイルのプレーンテキストにまとめる。kr1-corpus・kr5-corpus の整形に用いる変換器である。

```
git clone --depth 1 https://github.com/kanripo/KR1a0002
python3 scripts/kanripo_convert.py --repo KR1a0002 --out out/
python3 scripts/kanripo_convert.py --repo-dir clones/ --out out/   # 配下の KR* をすべて
```

出力の様式：`out/<類>/<ID>.txt`（例 `out/KR1a/KR1a0002.txt`。`--layout flat` で類フォルダを作らない）。BOMなしUTF-8・LF。頁マーカー【KR1a0002_WYG_001-1a】が独立した1行で、次の1行にその頁の本文全体が入る。`convert_report.tsv` に文献ごとの底本表示（BASEEDITION）・巻ファイル数・頁数・漢字数・外字参照の件数・pb 以外のタグの残存数・上流コミット・SHA-256 を出す。

整形規則：(1) 巻ファイルを名前順に読み、1作品1ファイルにまとめる。(2) 行頭が「#」の行はすべて捨てる（冒頭のメタデータ行のほか、本文途中の `# src:`・`# dating:`・`#+PROPERTY:` などを含む）。(3) `<md:…>`・`<img:…>` を除く。(4) 行末記号「¶」を除いて物理行を連結する（字下げの全角空白は残る）。(5) `<pb:X>` を【X】に変えて独立した1行にする。(6) 巻ファイルごとに末尾の空白を除き、巻と巻を改行1つでつなぐ（整形後に空になる巻は飛ばす。冒頭の空白は既定で残し、`--strip-head` で除く）。(7) 本文の文字は変えない（異体字の統一、外字参照 `&KR0001;` の置換、Unicode 正規化をしない）。規則に当たらない記法は本文に残り、件数が変換記録に出る。

回帰試験：kr5-corpus v1.1.0 の取得済1,650件を catalog.csv の commit 列のSHAで取り直して変換した結果は、1,649件がバイト単位で一致する。残る1件（KR5i0104）は、上流ファイルの先頭にBOMがあり、kr5-corpus 側の冒頭にBOMとメタデータ行が残っているための差である。本変換器はBOMを読み飛ばす（`--kr5-compat` を付けると kr5-corpus v1.1.0 と1,650件すべて一致する）。

## bkkbooks 変換器（v1.2.0追加）：scripts/bkkbooks_convert.py

bkkbooks（Kanseki Repository 次世代版、github.com/bkkbooks）の YAML スタンドオフ形式——本文 YAML と `assets/*.markers.yaml`（line-break・page-break・punctuation・indent・substitution 等のオフセット標識）——から、頁・段・行ID付きのプレーンテキストを生成する。基底層（bkkbooks の variant-fold 正規化済本文）と `editions/T`（大正蔵字体本文）の二層をそれぞれ `texts_norm/`・`texts_T/` に書き出し、substitution マーカーから正規化対応表 `variant-fold_restored.tsv` を復元して同梱する。

```
git clone --depth 1 https://github.com/bkkbooks/KR6t0136
python3 scripts/bkkbooks_convert.py --repo KR6t0136 --out out/
python3 scripts/bkkbooks_convert.py --repo-dir clones/ --out out/   # 配下の KR* をすべて
```

出力の様式：大正蔵の1行＝1行、行頭に `【T77.0303a04】`（巻.頁段行）。ファイル冒頭 `# ` 行に書誌（ID・題名・T番号・上流コミット・変換器版）、`## juan N` 行に巻境界。句読点・字下げの全角空白・訓点仮名などマーカーの content はその位置に挿入し、割注（voice/note、xml-element note）は（　）で囲む。不可視の U+200B・U+FFFC は既定で除去（`--keep-invisible`）。`convert_report.tsv` に文献ごとの行数・字数・二層の本文長一致・置換数を出す。TLS 由来（tls-texts）と CBETA 由来（xml-element・variant マーカーあり）の両方に対応。校異マーカー（variant）は `notes/variants_<ID>.tsv` に別出しし、本文には反映しない。

留意：bkkbooks の T 層では割注の多くが無標識で本文に連続している（標識があるのは一部のみ）。SAT 2018 Hanzi 版（KIT-2920）は割注の一部を欠くため、両者の字単位照合では bkkbooks 側だけにある字句として現れる。

将来の KR6 全体変換（KR6t 等の部単位）にもそのまま使える。
