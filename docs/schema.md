# Schema

所有输出 JSON 数组，每条记录至少含基础字段，类型特定字段按需扩展。

## 基础字段（所有记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 全局唯一，格式 `<source-key>#<seq>`，如 `shuowen#1` |
| `source` | string | 文献名，如 "说文解字" |
| `author` | string | 作者，如 "许慎" |
| `era` | string | 朝代，如 "汉" |
| `category` | string | 大类：字书 / 经 / 史 / 子 / 集 |
| `content` | string | 主文本（释义或正文） |

## 字书类（说文解字）

| 字段 | 类型 | 说明 |
|------|------|------|
| `char` | string | 字头 |
| `radical` | string | 部首，如 "一部" |
| `pinyin` | string | 现代拼音（来自殆知阁标注） |
| `fanqie` | string | 反切，如 "於悉切" |

## 经类（十三经）

| 字段 | 类型 | 说明 |
|------|------|------|
| `chapter` | string | 篇名，如 "学而" |
| `section` | int | 章节序号 |

## 史类（资治通鉴）

| 字段 | 类型 | 说明 |
|------|------|------|
| `volume` | int | 卷号 |
| `period` | string | 朝代时段，如 "周纪" |

## 示例

```json
{
  "id": "shuowen#1",
  "source": "说文解字",
  "author": "许慎",
  "era": "汉",
  "category": "字书",
  "char": "一",
  "radical": "一部",
  "pinyin": "yi1",
  "fanqie": "於悉切",
  "content": "惟初太始，道立於一，造分天地，化成萬物。凡一之屬皆从一。"
}
```
