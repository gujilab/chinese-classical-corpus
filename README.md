# classical-corpus

中国古典文献结构化语料集 — 把殆知阁等公开文本转为统一 JSON schema，可直接喂给任何 LLM 训练或评测。

**当前版本：v0.3** — 12/13 十三经 + 说文解字 + 资治通鉴，约 540 万字，10,694 条记录。

## 覆盖

| 类别 | 文献 | 条数 | 字数 | 状态 |
|------|------|------|------|------|
| 字书 | 说文解字 | 9,831 | 140K | 21% 字头为 □（CJK 扩展生僻字） |
| 经-四书 | 大学 | 1 | 2K | ✓ |
| 经-四书 | 中庸 | 1 | 4K | ✓ |
| 经-四书 | 论语 | 20 | 22K | ✓ |
| 经-四书 | 孟子 | 14 | 46K | ✓ |
| 经-五经 | 诗经 | 305 | 38K | ✓ |
| 经-五经 | 尚书 | 55 | 34K | 缺 3 篇（殆知阁源文无正文） |
| 经-五经 | 礼记 | 47 | 131K | 殆知阁合并了曲礼/檀弓/杂记上下 |
| 经-五经 | 周易 | 67 | 34K | 64 卦 + 4 传序（缺卦三、系辞上） |
| 经-五经 | 春秋左传 | 12 | 264K | 按 12 公组织 |
| 经-传记 | 春秋公羊传 | 12 | 75K | ✓ |
| 经-传记 | 春秋穀梁传 | — | — | **TODO（殆知阁仅有注疏版）** |
| 经-传记 | 孝经 | 18 | 2K | ✓ |
| 经-传记 | 尔雅 | 19 | 20K | ✓ |
| 史 | 资治通鉴 | 292 | 4.67M | 卷 158、171 殆知阁缺正文 |

## 用法

```python
from datasets import load_dataset
ds = load_dataset('json', data_files='output/corpus.jsonl', split='train')
print(ds[0])
# {'id': 'shuowen#1', 'source': '说文解字', 'author': '许慎', 'era': '汉',
#  'category': '字书', 'char': '一', 'radical': '一部', ...}
```

或者按分类用单独 JSON：

```python
import json
shijing = json.load(open('output/wujing/shijing.json'))
```

## Schema

通用字段（所有记录）：`id` `source` `author` `era` `category` `content`

类型特定字段：
- 字书：`char` `radical` `pinyin` `fanqie`
- 经类：`chapter` `subchapter` `section` `title`
- 史类：`volume` `period`

详见 [docs/schema.md](docs/schema.md)。

## 数据来源

- **[殆知阁古代文献](https://github.com/garychowcmu/daizhigev20)** — 主要语料源（17 亿字），原始为 plain text
- **[chinese-poetry](https://github.com/chinese-poetry/chinese-poetry)** — 诗经 + 四书 已是 JSON
- 源数据未托管在本仓库，需自行 clone（约 2.1GB git size / 6.9GB 解压）

## 重新生成

```bash
# 设置 daizhige 路径（默认 ~/Documents/zion/reference/Chinese/classical/corpora/daizhigev20）
python scripts/extract_shuowen.py
python scripts/extract_sishu.py
python scripts/extract_shijing.py
python scripts/extract_wujing_others.py
python scripts/extract_remaining_classics.py
python scripts/extract_zizhi_tongjian.py
python scripts/build_corpus.py    # 合并 → corpus.jsonl + stats.md
```

## 已知数据问题

源自殆知阁原文的瑕疵，已记录但未修改：

- 说文 □ 字头：2102 字头是 `□` 占位符（CJK Extension B-G 区生僻字源文未渲染）
- 资治通鉴卷 158、171：源文中只有标题占位符，无正文
- 资治通鉴卷 258：作者属字误为 `寀`，实为 `宋`
- 周易缺卦三（屯）和系辞上：源文格式异常未匹配
- 尚书缺 3 篇（益稷、禹贡、泰誓上）：源文 TOC 列出但无正文

## 路线图

- **v0.4** — 补全穀梁传（ctext.org 爬虫）；用 cjkvi-ids 修复说文 □ 字头
- **v0.5** — 加二十四史前 4 部（史记、汉书、后汉书、三国志）
- **v1.0** — 加古译今对齐数据（指令微调集）

## License

数据集 (`output/`) 用 **CC0**，代码 (`scripts/`) 用 **MIT**。详见 [LICENSE](LICENSE)。
