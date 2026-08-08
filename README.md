# corpus-search-toolkit

宗教文献コーパス群（pali・kanseki・kr5・gretil・sarit・dcs・muktabodha・84000-tm・cdsl）の横断検索における綴り揺れ対策の標準手順とツールである。固有名詞検索で母音長短の揺れにより偽ゼロが生じた事例（vajiriya で検索し vājiriyā を取り逃す）の再発防止を目的とする。

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
| kanseki / kr5 | 漢文コーパス | 本手順の対象外（漢字表記の異体字問題は別途） |

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

## 出力の様式

- マトリクスTSV：`label / corpus / files_with_hits / total_hits`。報告にはこの表と各labelの正規表現を対で掲げる
- KWIC TSV：`label / corpus / file / match / pre / post`（前後60字）。引用時は各コーパスの原ファイル（sarit は texts/ の原符号化）に立ち返って確認する
- ヒット0の報告には「当該正規表現・当該rootの範囲で0」という限定を付す（コーパス未収録文献の存在——Pradīpoddyotana 等——による見かけの0と区別するため）

## 依存

Python 3 標準ライブラリのみ（外部パッケージ不要）。

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
