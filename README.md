# classical-corpus

中国古典文献结构化语料集 — 把殆知阁、wikisource、shuowenjiezi 等公开文本转为统一 JSON schema，可直接喂给任何 LLM 训练或评测。

**当前版本：v0.7** — 完整十三经 + 说文解字 + 资治通鉴 + 二十四史前 9 部，~1360 万字，11,507 条记录。

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
| 尚书 | 55 | 34K | 殆知阁 |
| 礼记 | 47 | 131K | 殆知阁 |
| 周易 | 67 | 34K | 殆知阁 |
| 春秋左传 | 12 | 264K | 殆知阁 |
| 春秋公羊传 | 12 | 75K | 殆知阁 |
| 春秋穀梁传 | 12 | 42K | wikisource (繁→简) |
| 孝经 | 18 | 2K | 殆知阁 |
| 尔雅 | 19 | 20K | 殆知阁 |

### 二十四史前 9 部
| 文献 | 条数 | 字数 | 作者 | 来源 |
|------|------|------|------|------|
| 史记 | 130 | 1.11M | 司马迁 | 殆知阁四库版 |
| 汉书 | 101 | 895K | 班固 | 殆知阁 |
| 后汉书 | 130 | 1.21M | 范晔 | 殆知阁四库版 |
| 三国志 | 65 | 734K | 陈寿 | 殆知阁 |
| 晋书 | 129 | 1.43M | 房玄龄等 | 殆知阁 |
| 宋书 | 99 | 1.01M | 沈约 | 殆知阁 |
| 南齐书 | 57 | 358K | 萧子显 | 殆知阁 |
| 梁书 | 55 | 349K | 姚思廉 | 殆知阁 |
| 陈书 | 35 | 187K | 姚思廉 | 殆知阁 |

### 编年史
| 文献 | 条数 | 字数 |
|------|------|------|
| 资治通鉴 | 292 | 4.67M |

## 用法

```python
from datasets import load_dataset
ds = load_dataset('json', data_files='output/corpus.jsonl', split='train')
print(ds[0])
```

## Schema

通用字段（所有记录）：`id` `source` `author` `era` `category` `content`

类型特定字段：
- 字书：`char` `radical` `pinyin` `fanqie`
- 经类：`chapter` `subchapter` `section` `title`
- 史类：`volume` `chapter`

详见 [docs/schema.md](docs/schema.md)。

## 数据来源

- **[殆知阁古代文献](https://github.com/garychowcmu/daizhigev20)** — 主要语料源（17 亿字 plaintext）
- **[chinese-poetry](https://github.com/chinese-poetry/chinese-poetry)** — 诗经 + 四书 已是 JSON
- **[zh.wikisource.org](https://zh.wikisource.org/wiki/春秋穀梁傳)** — 穀梁传（殆知阁仅有注疏版）
- **[shuowenjiezi/shuowen](https://github.com/shuowenjiezi/shuowen)** — 说文 □ 字修复的交叉参考源

源数据未托管在本仓库，需自行 clone。

## 重新生成

```bash
pip install opencc-python-reimplemented   # 仅 scrape_guliang.py + fix_shuowen_boxes.py 需要

python scripts/extract_shuowen.py
python scripts/fix_shuowen_boxes.py        # 修复 1746 个 □ 字头
python scripts/extract_sishu.py
python scripts/extract_shijing.py
python scripts/extract_wujing_others.py
python scripts/extract_remaining_classics.py
python scripts/scrape_guliang.py            # 网络爬取，~15 秒
python scripts/extract_zizhi_tongjian.py
python scripts/extract_histories.py         # 9 部正史
python scripts/build_corpus.py              # 合并 → corpus.jsonl + stats.md
```

## 已知数据问题

- **说文 356 字仍为 □** (3.6%)：shuowenjiezi/shuowen 中也无对应或反切歧义
- **资治通鉴卷 158、171**：殆知阁源文中只有标题占位符（v0.8 计划补）
- **资治通鉴卷 258**：作者属字误为 `寀`，实为 `宋`
- **周易缺卦三、系辞上**：源文格式异常未匹配
- **尚书缺 3 篇**（益稷、禹贡、泰誓上）：源文 TOC 列出但无正文

## 路线图

- **v0.8** — 补全资治通鉴 158/171 + 尚书/周易缺漏（需自定义 wikisource/ctext 爬虫）
- **v0.9** — 加二十四史下 6 部（魏书、北齐书、周书、南史、北史、隋书）
- **v1.0** — 加古译今对齐数据（指令微调集）
- **v1.x** — 加部首/字形分解维度（结合 cjkvi-ids，做表意建模数据）

## License

数据集 (`output/`) 用 **CC0**，代码 (`scripts/`) 用 **MIT**。详见 [LICENSE](LICENSE)。
