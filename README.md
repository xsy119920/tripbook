# tripbook

把一份行程 JSON 渲染成 A5 小册子。HTML 排版，Chromium 打印，输出 PDF。

给需要带家人出门的人用。纸面上只有三样东西：路线、每天的时间、要当心的事。不放评分，不放推荐指数，不放二维码。

一册 14 页，A5，中文字体用华文中宋配等线。

![全部页面](docs/preview.png)

## 需要什么

- Python 3.9 以上，只用标准库
- 一个 Chromium 系浏览器：Edge、Chrome 或 Chromium
- 字体：华文中宋（`STZhongsong`）与等线（`DengXian`），Windows 自带。macOS 和 Linux 上换成思源宋体、思源黑体，改 `design/doc.css` 顶部的两个变量即可

## 用

```bash
python make.py trips/chaoshan.json
```

输出：

```
book.html            中间文件，可以直接用浏览器打开看
out/潮汕三天两晚.pdf   小册子
out/preview.png      加 --png 才有，全部页面的缩略图
```

指定浏览器：

```bash
TRIPBOOK_BROWSER=/usr/bin/chromium python make.py trips/chaoshan.json
```

只要 HTML 不要 PDF：

```bash
python make.py trips/chaoshan.json --html-only
```

## 写数据

一册书就是 `pages` 数组，按顺序排。页面的编号自己填在 `no` 里，左下角的页码是自动的。

```json
{
  "title": "潮汕三天两晚",
  "output": "潮汕三天两晚.pdf",
  "pages": [
    { "type": "cover", "place": "广东潮汕，自驾", "title": "潮汕三天两晚",
      "sub": "汕头老城到潮州古城", "image": "photos/cover.jpg",
      "facts": [["11月18日到20日", "三天两晚"]] }
  ]
}
```

页面类型：

| type | 用途 | 主要字段 |
|---|---|---|
| `cover` | 封面，整页照片压字 | `image` `title` `sub` `place` `facts` |
| `overview` | 三天怎么走 | `rows` `lede` `note` `facts` |
| `rules` | 注意事项，编号列表 | `items` `quote` `note` `facts` |
| `route` | 路线与停车 | `stops` `rows` `facts` |
| `spread` | 看图，一张大图两张小图 | `hero` `heroCaption` `a` `aCaption` `b` `bCaption` |
| `day` | 一天的时间表 | `rows` `note` `box` |
| `food` | 吃什么 | `hero` `heroCaption` `second` `secondCaption` `box` |
| `budget` | 预算条 | `items` `total` `totalNote` `note` `facts` |
| `checklist` | 出发前清单 | `items` `box` |
| `back` | 封底 | `image` `title` `sub` `credit` |

`rows` 的每一项是 `[时间, 标题, 小字]`，`items` 是 `[正文, 小字]`，`facts` 是 `[数字, 说明]`。

图片路径相对 `trips/` 或仓库根目录都行。

## 为什么它不像 AI 生成的

这份排版是按几条硬规则做的，写在这里，改的时候别破坏：

1. 颜色只有五个：纸、墨、灰、墨蓝、细线。全部在 `design/doc.css` 的 `:root` 里，正文里不出现色值。
2. 不用卡片、不用阴影、不用圆角面板。分区分靠 0.3 到 0.4 磅的细线。
3. 字族最多两个：标题华文中宋，正文等线。
4. 一页只说一件事。文字放不下就减字，不缩字号。
5. 没有图标，没有 emoji，没有勾选符号。需要的强调用朱红和字重。
6. 不放假的数字。预算、里程、步数、人均，都是能在出发前算出来的。
7. 不使用「必去」「绝美」「天花板」这类词。

`design/doc.css` 开头的注释是这套规则的版本戳。

## 这套版式从哪来

用 [Hallmark](https://github.com/tripbook/hallmark) 的设计方法做的。跑它的抽签，抽到 **Specimen**：

> 暖燕麦纸，近黑的墨，高对比衬线压在无衬线正文上，1px 方线，唯一的墨蓝信号。

颜色和线宽照抄了它的 token。字体做了替换：Specimen 用 Bodoni Moda 和 Geist，都没有中文字形，换成华文中宋（高对比衬线，对应 Bodoni）和等线（中性无衬线，对应 Geist）。两处刻意的偏离：照片保留彩色（Specimen 原本是墨色双色调），封面允许字压在图上（它原本规定字不落在照片上）。

## 已知限制

- 只出 A5。要 A4 或 A6，改 `design/doc.css` 里的 `@page` 和 `.sheet` 尺寸，再调一遍行距。
- 中文竖排、双栏、目录、页码索引都没有。
- 不查实时信息。门票、开放时间、闭馆日、天气，都要自己核对了再写进 JSON。
- 示例里的图片来自公开网络，只适合家庭内部使用。要公开发布，换成自己拍的或带授权的图。

## 目录

```
make.py            渲染与打印
trips/             行程数据，一册一个 json
design/doc.css     版式与颜色
design/preview.css 只在缩略图时加载
photos/            图片
docs/              截图
out/               输出，不进仓库
```

## 许可

MIT，见 [LICENSE](LICENSE)。
