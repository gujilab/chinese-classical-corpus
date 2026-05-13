# classical-corpus

[![data license](https://img.shields.io/badge/data-CC0--1.0-green)](LICENSE) [![code license](https://img.shields.io/badge/code-MIT-yellow)](LICENSE) [![HF dataset](https://img.shields.io/badge/%F0%9F%A4%97-dataset-blue)](https://huggingface.co/datasets/gujilab/chinese-classical-corpus) [![HF bench](https://img.shields.io/badge/%F0%9F%A4%97-bench-orange)](https://huggingface.co/datasets/gujilab/chinese-classical-bench)

> 📦 **Available on HuggingFace Datasets**: [gujilab/chinese-classical-corpus](https://huggingface.co/datasets/gujilab/chinese-classical-corpus) — load via `datasets.load_dataset()` without rebuilding from sources.
>
> 🎯 **配套评测基准**: [gujilab/chinese-classical-bench](https://github.com/gujilab/chinese-classical-bench) ([🤗 gujilab/chinese-classical-bench](https://huggingface.co/datasets/gujilab/chinese-classical-bench)) — 500 道题 × 5 任务，测 LLM 古典文献能力

中国古典文献结构化语料集 — 把殆知阁、wikisource、ctext.org、shuowenjiezi、chtxt、hunterhug 等公开文本转为统一 JSON schema，可直接喂给任何 LLM 训练或评测。

**当前版本：v1.3** — 1724 万字源语料（v1.3 补全南史卷 2/7/68/74 → 80/80 卷完整）+ **指令微调数据集**：
- 古译今 + 今译古 双向翻译: **192 万条** (640 MB jsonl, NiuTrans 来源)
- 断句加标点: **4.9 万条** (60 MB jsonl)
- 总计 **197 万条指令记录**，覆盖 97 部典籍

详见 [output/instruct/README.md](output/instruct/README.md).

## 覆盖

### 字书
| 文献 | 条数 | 字数 | 来源 | 状态 |
|------|------|------|------|------|
| 说文解字 | 9,831 | 140K | 殆知阁 + shuowenjiezi/shuowen | □ 修复至 3.6%（剩 356 难字） |

### 十三经（完整）
| 文献 | 条数 | 字数 | 来源 |
|------|------|------|------|
| 大学 | 1 | 2K | chinese-poetry |
| 中庸 | 1 | 4K | chinese-poetry |
| 论语 | 20 | 22K | chinese-poetry |
| 孟子 | 14 | 46K | chinese-poetry |
| 诗经 | 305 | 38K | chinese-poetry |
| 尚书 | 57 | 36K | 殆知阁 + ctext.org（益稷/禹贡补全）|
| 礼记 | 47 | 131K | 殆知阁 |
| 周易 | 69 | 37K | 殆知阁 + ctext.org（屯卦/系辞上补全）|
| 春秋左传 | 12 | 264K | 殆知阁 |
| 春秋公羊传 | 12 | 75K | 殆知阁 |
| 春秋穀梁传 | 12 | 42K | wikisource (繁→简) |
| 孝经 | 18 | 2K | 殆知阁 |
| 尔雅 | 19 | 20K | 殆知阁 |

### 二十四史前 15 部（v0.10 多源融合）
| 文献 | 条数 | 字数 | 主要来源 |
|------|------|------|---------|
| 史记 | 130 | 1.11M | 殆知阁四库版 |
| 汉书 | 101 | 895K | 殆知阁 |
| 后汉书 | 130 | 1.21M | 殆知阁四库版 |
| 三国志 | 65 | 734K | 殆知阁 |
| 晋书 | 128 | 1.43M | chtxt (繁→简) |
| 宋书 | 100 | 1.00M | chtxt (繁→简) |
| 南齐书 | 59 | 351K | chtxt (繁→简) |
| 梁书 | 56 | 360K | chtxt (繁→简) |
| 陈书 | 36 | 198K | chtxt (繁→简) |
| 魏书 | 130 | 1.23M | chtxt (繁→简) |
| 北齐书 | 49 | 261K | chtxt (繁→简) |
| 周书 | 49 | 318K | 殆知阁 |
| 南史 | 80 | 365K | NiuTrans/Classical-Modern + wikisource (vols 2/7/68/74 补全) |
| 北史 | 99 | 1.36M | chtxt (繁→简) |
| 隋书 | 85 | 866K | chtxt (繁→简) |

### 编年史
| 文献 | 条数 | 字数 | 状态 |
|------|------|------|------|
| 资治通鉴 | 294 | 4.70M | 完整（卷158/171 殆知阁基础版补全）|

## 用法

```python
from datasets import load_dataset
ds = load_dataset('json', data_files='output/corpus.jsonl', split='train')
print(ds[0])
```

## Schema

通用字段：`id` `source` `author` `era` `category` `content`

类型特定字段：
- 字书：`char` `radical` `pinyin` `fanqie`
- 经类：`chapter` `subchapter` `section` `title`
- 史类：`volume` `volume_suffix` `chapter`

详见 [docs/schema.md](docs/schema.md)。

## 数据来源

- **[殆知阁](https://github.com/garychowcmu/daizhigev20)** — 主要语料源
- **[chinese-poetry](https://github.com/chinese-poetry/chinese-poetry)** — 诗经 + 四书
- **[zh.wikisource.org](https://zh.wikisource.org)** — 穀梁传
- **[ctext.org](https://ctext.org)** — 尚书/周易 缺漏补全
- **[shuowenjiezi/shuowen](https://github.com/shuowenjiezi/shuowen)** — 说文 □ 字修复
- **[chtxt](https://github.com/JasonWade001/chtxt)** — 二十四史清洁版（9 部 繁→简）
- **[NiuTrans/Classical-Modern](https://github.com/NiuTrans/Classical-Modern)** — 南史 76 卷 + 古译今 192 万对句
- **[zh.wikisource.org](https://zh.wikisource.org/wiki/南史)** — 南史 卷 2/7/68/74（NiuTrans 缺漏补全）

## 重新生成

```bash
pip install opencc-python-reimplemented

python scripts/extract_shuowen.py
python scripts/fix_shuowen_boxes.py
python scripts/extract_sishu.py
python scripts/extract_shijing.py
python scripts/extract_wujing_others.py
python scripts/extract_remaining_classics.py
python scripts/scrape_guliang.py
python scripts/fill_gaps.py
python scripts/extract_zizhi_tongjian.py
python scripts/extract_histories.py
python scripts/patch_alternates.py    # 资治通鉴 158/171 + chtxt 替换
python scripts/scrape_nanshi_missing.py  # 南史 卷 2/7/68/74 从 wikisource 补全 (v1.3)
python scripts/build_corpus.py
```

## 已知数据问题

- **说文 356 字仍为 □** (3.6%)：shuowenjiezi/shuowen 中也无对应或反切歧义
- ~~**南史**: 76/80 卷 (NiuTrans 提供，缺最末 4 卷)~~ **已修复** (v1.3) — 卷 2/7/68/74 从 wikisource 补全，现 80/80 卷完整
- **资治通鉴卷 258 字误**：源文中作者属字误为 `寀`，实为 `宋`

## 路线图

- ✅ **v1.3** — 南史 80/80 卷完整（wikisource 补全卷 2/7/68/74）
- **v1.4** — 部首/字形分解维度（cjkvi-ids 整合做表意建模辅助数据）
- **v1.5** — 古文阅读理解 Q&A
- **v2.0** — 加二十四史下 9 部（旧/新唐书、旧/新五代史、宋史、辽金元明史）

## License

数据集 (`output/`) 用 **CC0**，代码 (`scripts/`) 用 **MIT**。详见 [LICENSE](LICENSE)。
