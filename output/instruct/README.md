# Instruction Tuning Datasets

任务化的训练数据集，可直接用于 LoRA / SFT 训练。所有数据为 JSONL 格式，每行一条指令记录。

## Files

| 文件 | 任务 | 条数 | 大小 |
|------|------|------|------|
| `translate.jsonl` | 古译今 (c2m) + 今译古 (m2c) | 1,922,902 | ~640 MB |
| `punctuate.jsonl` | 断句加标点 | 46,078 | ~57 MB |

**总计：1,968,980 条 / 约 697 MB（全部 □-free）**

> 数据已过滤掉所有含 □ 占位符（殆知阁源中无法渲染的 CJK 扩展字）的句对，
> 影响约 0.2% 记录。corpus.jsonl 中的 □ 字符（散布在长篇章节里）保留，因为
> 它们是中华书局点校本等学术版本的常态特征，不影响章节级训练用途。

## 数据 Schema

每条记录通用字段：
```json
{
  "id": "...",
  "task": "c2m | m2c | punctuate",
  "instruction": "...",  // 指令模板 (轮换多个表达)
  "input": "...",
  "output": "...",
  "source": "论语·学而",  // 出处
  "category": "经 | 史 | 子 | 集"
}
```

## Translate 数据来源

`translate.jsonl` 来源 [NiuTrans/Classical-Modern](https://github.com/NiuTrans/Classical-Modern) (MIT License)，覆盖 **97 部典籍 / 97 万句对**，每对生成 c2m + m2c 双向指令记录。

### Top 15 books by record count
- 资治通鉴: 240,756
- 明史: 187,204
- 太平广记: 167,358
- 宋史: 109,388
- 汉书: 78,850
- 史记: 60,768
- 旧唐书: 58,484
- 北史: 57,460
- 魏书: 56,476
- 宋书: 53,968
- 后汉书: 53,656
- 新唐书: 52,332
- 晋书: 52,324
- 元史: 48,410
- 徐霞客游记: 43,324

### 指令变体（去单一性）

c2m 指令轮换：
- 将下列古文翻译成现代汉语：
- 把这句文言文译成白话文：
- 请用现代汉语翻译这段古文：
- 解释下列古文的含义：
- 翻译：
- 用白话解释这句古文：

m2c 指令轮换：
- 将下列现代汉语翻译成古文：
- 用文言文表达这句话：
- 把这段白话改写为古文：
- 请用古文表达：

### 过滤规则
- 句长 < 4 字 或 > 500 字 剔除
- 古今长度比 > 10x 剔除（疑似对齐错位）

## Punctuate 数据来源

由 `corpus.jsonl` 生成 — 拿干净有标点的古文，去掉标点作为 input，原文作为 output。**~5 万条覆盖 14 部正史 + 4 部经传**。

## 用法

```python
from datasets import load_dataset
ds = load_dataset("json",
    data_files={
        "translate": "output/instruct/translate.jsonl",
        "punctuate": "output/instruct/punctuate.jsonl"
    })
print(ds["translate"][0])
```

## 重新生成

```bash
python scripts/build_instruct.py        # 古译今 + 今译古
python scripts/build_punctuation.py     # 断句加标点
```

`build_instruct.py` 需先 clone NiuTrans/Classical-Modern 到 `~/Documents/zion/reference/Chinese/classical/corpora/`。

## License

CC0 — 无附加限制。底层 NiuTrans 数据是 MIT，源典籍是公有领域。
