---
license: cc0-1.0
language:
  - zh
task_categories:
  - text-generation
  - translation
tags:
  - chinese-classical
  - 古文
  - 文言文
  - instruction-tuning
  - llm
size_categories:
  - 1M<n<10M
configs:
  - config_name: corpus
    data_files:
      - split: train
        path: "corpus.jsonl"
  - config_name: translate
    data_files:
      - split: train
        path: "translate.jsonl"
  - config_name: punctuate
    data_files:
      - split: train
        path: "punctuate.jsonl"
---

# Chinese Classical Corpus

中国古典文献结构化语料集，含完整十三经 + 说文解字 + 资治通鉴 + 二十四史前 15 部，以及 197 万条古译今/今译古/断句指令对。

**全部 CC0 公有领域，可商用、可改用、无附加限制。**

## Quick Start

```python
from datasets import load_dataset

# 源语料 (12,005 条章节级记录, 17.2M 字)
corpus = load_dataset("dzxr/chinese-classical-corpus", "corpus", split="train")

# 古译今 / 今译古 双向指令数据 (1,924,378 条)
translate = load_dataset("dzxr/chinese-classical-corpus", "translate", split="train")

# 断句加标点指令 (46,546 条)
punctuate = load_dataset("dzxr/chinese-classical-corpus", "punctuate", split="train")

print(corpus[0])
# {'id': 'shuowen#1', 'source': '说文解字', 'author': '许慎', 'era': '汉',
#  'category': '字书', 'char': '一', 'radical': '一部', ...}
```

## Configs

### `corpus` — 源语料

12,005 条章节/篇/卷级别的清洁文本，覆盖 30 部典籍：

| 类别 | 文献 | 备注 |
|------|------|------|
| 字书 | 说文解字 (9,831 字头) | 21% 字头修复至 3.6% (CJK Ext B-G 通过 [shuowenjiezi/shuowen](https://github.com/shuowenjiezi/shuowen) 交叉补全) |
| 经 (十三经) | 论语、孟子、大学、中庸、诗经、尚书、礼记、周易、春秋左传/公羊传/穀梁传、孝经、尔雅 | 完整 |
| 史 | 史记、汉书、后汉书、三国志、晋书、宋书、南齐书、梁书、陈书、魏书、北齐书、周书、南史、北史、隋书 (二十四史前 15 部) | |
| 编年 | 资治通鉴 294 卷 | 完整 |

**通用字段**：`id` `source` `author` `era` `category` `content`
**类型特定**：字书加 `char/radical/pinyin/fanqie`，经类加 `chapter/section`，史类加 `volume`

### `translate` — 古译今 / 今译古

1,924,378 条指令记录，覆盖 97 部典籍。来源：[NiuTrans/Classical-Modern](https://github.com/NiuTrans/Classical-Modern) (MIT) 双语数据。

```json
{
  "id": "instruct#1",
  "task": "c2m",
  "instruction": "将下列古文翻译成现代汉语：",
  "input": "子曰：学而时习之，不亦说乎？",
  "output": "孔子说：学了知识然后按一定的时间复习它，不也是很愉快吗？",
  "source": "论语·学而篇",
  "category": "经"
}
```

- `task`: `c2m` (古→今) 或 `m2c` (今→古)
- 6 种 c2m 指令 + 4 种 m2c 指令模板，轮换使用
- 798 条记录有 `_has_box: true` flag — 含古籍散佚 □ 占位符（参见下方说明）

### `punctuate` — 断句加标点

46,546 条记录，从 `corpus` 中抽取章节段，去掉标点作为输入，原文作为输出。覆盖 14 部正史 + 经传。

```json
{
  "id": "punct#1",
  "task": "punctuate",
  "instruction": "为下列古文添加标点：",
  "input": "夫天地者万物之逆旅也光阴者百代之过客也",
  "output": "夫天地者，万物之逆旅也；光阴者，百代之过客也。",
  "source": "晋书",
  "category": "史"
}
```

## 关于 □ 字符

NiuTrans 源中 1,266 条记录含 □（占指令数据 0.06%），分两类：

1. **可恢复（678 条已修复）** — 通过 chtxt 繁体版交叉补全。例：`营昭阳殿，□令监造` → `营昭阳殿，𠡠令监造`（𠡠 是 CJK Ext B U+2086D 的"敕"异体字）
2. **不可恢复（798 条加 `_has_box: true`）** — 古籍散佚（逸周书）、出土文献残损（孙膑兵法竹简）、帛书重建（黄帝四经）、礼乐符号（礼记节奏记号）

训练时按需过滤：`ds.filter(lambda x: not x.get("_has_box", False))`

## 数据来源

- [殆知阁古代文献](https://github.com/garychowcmu/daizhigev20) — 主要语料源
- [chinese-poetry](https://github.com/chinese-poetry/chinese-poetry) — 诗经 + 四书
- [zh.wikisource.org](https://zh.wikisource.org) — 穀梁传
- [ctext.org](https://ctext.org) — 尚书/周易缺漏补全
- [shuowenjiezi/shuowen](https://github.com/shuowenjiezi/shuowen) — 说文 □ 字修复
- [chtxt](https://github.com/JasonWade001/chtxt) — 二十四史清洁版繁体（9 部 繁→简）
- [NiuTrans/Classical-Modern](https://github.com/NiuTrans/Classical-Modern) (MIT) — 古译今对齐 + 南史 76 卷

## 已知数据问题

- **说文 356 字仍为 □** (3.6%)：跨参考源也无法消歧
- **资治通鉴 卷 258**：源文中作者属字误为 `寀` (cǎi)，实为 `宋` (sòng)
- **南史 76/80 卷**：NiuTrans 上游缺最末 4 卷
- **生僻字 ASCII 化**：极个别 CJK Ext G 字符在转换中可能丢失

## 路线图

- v1.3 — 加二十四史下 9 部（旧/新唐书、旧/新五代史、宋史、辽金元明史 + 清史稿）
- v1.x — 部首/字形分解维度（cjkvi-ids 整合，做表意建模辅助数据）
- v2.0 — 古文阅读理解 Q&A（GPT 辅助生成）

## 引用

```bibtex
@misc{chinese-classical-corpus,
  title  = {Chinese Classical Corpus},
  author = {dzxr},
  year   = {2026},
  url    = {https://huggingface.co/datasets/dzxr/chinese-classical-corpus}
}
```

代码仓库：https://github.com/zi6me/chinese-classical-corpus

## License

**CC0 1.0 Universal** — 公有领域，无附加限制。源典籍本就是公有领域；本数据集对它们的结构化处理也以 CC0 释出。

底层依赖各自的 license 详见 [LICENSE](LICENSE)。
