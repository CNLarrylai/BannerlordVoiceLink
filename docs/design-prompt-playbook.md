# 设计 Prompt 工程 Playbook —— 让 AI 出好看的 UI

> 目的: 解决"AI 出的设计能用但巨丑、没风格"的问题。附**可直接粘贴**的 prompt 模板。
> 依据: Anthropic 官方前端美学指南 + PROMPT 框架 + 设计 token 实践 (见文末来源)。

---

## 0. 为什么会丑 (先理解, 再解决)

AI 会**向训练分布的中心收敛** —— 你越不给方向, 它越吐出最平庸的"平均值":
Bootstrap 卡片、Inter 字体、紫色渐变白底。官方管这叫 **"AI slop"**。

> **核心结论: 丑 = 约束不够。** "设计得好看一点"必然出垃圾;
> 好设计来自**大量具体约束 + 明确要它偏离平庸**。

---

## 1. 万能骨架: PROMPT 六要素

每个界面的 prompt 都按这六项填满, 别留空:

| 字母 | 含义 | 你的项目怎么填 |
|---|---|---|
| **P**latform | 平台/尺寸 | "桌面浮层, 360×180px, 常驻游戏画面之上" |
| **R**ole | 谁在用/目的 | "游戏主播直播中指挥军队; 观众通过它看懂指令" |
| **O**utput | 屏幕类型/元素/**真实内容** | "状态图标 + 兵种名 + 指令名; 例:弓箭手·盾墙" |
| **M**ood | **风格名 + 色板 + 字体 + 气质** | 见 §3 (这一项决定 80% 的观感) |
| **P**atterns | 布局/组件模式 | "左图标 + 右文字两栏; 印章式成功反馈" |
| **T**echnical | 技术约束/状态 | "深色主题; 背景纯色可抠像(OBS); 出四个状态" |

**最容易被忽略、最致命的是 M(Mood)。** 没有它, AI 每次都给你蓝配白。

---

## 2. 五条"反平庸"硬技法 (Anthropic 官方)

1. **字体要独特** —— **禁用 Inter / Roboto / Arial / 系统默认**。
   - 用有个性的: 编辑感衬线(Playfair/Fraunces)、技术感(IBM Plex)、展示体(Clash Display)。
   - 中文见 §3。**字重对比拉满**(100 vs 900, 别 400 vs 600); **字号跳跃 3 倍以上**。
2. **一个主色 + 一个尖锐强调色** —— 别搞"雨露均沾"的彩虹配色。深色主调 + 一抹高饱和点睛。
3. **背景要有氛围和层次** —— 别用纯色填充; 叠 CSS 渐变、几何纹理、材质。
4. **动效集中在高光时刻** —— 一次编排好的"入场动画"(错峰渐显)胜过一堆零碎微交互。
5. **显式列出要避开的东西** —— 把"AI slop 清单"写进 prompt(见 §4 负面清单)。

---

## 3. 本项目的美术方向 (直接用, 别再"中世纪风"这么泛)

给 AI 一个**具体、有出处**的方向, 它才不会瞎编。我们锁定:

**主题词: 点将台 · 传令 · 兵符 · 水墨与鎏金 (Ink-and-Bronze War Council)**

- **参考锚点 (让 AI "像这个"):**
  - **《全面战争:三国》(Total War: Three Kingdoms) 的 UI** ← 最佳参考, 中式战争 + 水墨/印章/玉石/青铜, 做得极美
  - 骑砍2 指令轮盘 (功能结构参考)
  - 中国水墨画留白、圣旨/传令卷轴、虎符兵符、朱砂印章
- **色板 (主色 + 尖锐强调, 都给 hex):**
  - 底: 陈墨黑带暖调 `#14100C` ~ `#1E1813` (不要纯黑)
  - 主材质: 做旧鎏金/青铜 `#C9A24B`(带磨损明暗, 不要死金)
  - **点睛: 朱砂红印章 `#B23A2E`** ← 成功执行时盖章用, 全局唯一的高饱和
  - 表面高光: 宣纸/羊皮 `#E8DCC0`
- **字体 (中文, 都可商用/开源, 适合分发):**
  - 标题/指令名: **思源宋体 Heavy**(Source Han Serif) 或 **霞鹜文楷**(LXGW WenKai) —— 有笔锋、庄重
  - 想更"军令"感: 隶书/魏碑类展示体(注意授权)
  - 数据/小字: **思源黑体 / HarmonyOS Sans** —— 清晰
- **材质/纹理:** 宣纸颗粒、水墨晕染边缘、青铜浮雕/刻字、旌旗剪影。
- **气质关键词:** 肃杀、庄重、有重量感、留白克制、光从暗处透出。

---

## 4. 负面清单 (每个 prompt 都附上)

```
避免这些 AI 默认的平庸做法:
- 字体: 禁用 Inter / Roboto / Arial / 系统默认字体
- 配色: 禁用紫色渐变白底、蓝配白、彩虹均分色
- 布局: 禁用千篇一律的 Bootstrap 圆角卡片堆叠
- 图标: 不要用 emoji 当图标
- 不要科技蓝/赛博朋克/霓虹, 与冷兵器战争调性冲突
- 不要纯黑背景(用带暖调的陈墨黑)、不要死板的纯色填充
```

---

## 5. 可直接粘贴的模板

### 5A. 通用"风格锁"(放在每个 prompt 最前面)

```
You are an award-winning art director for AAA strategy-game UI (think Total
War: Three Kingdoms). Design in an "Ink-and-Bronze War Council" aesthetic:
aged ink-black background (#14100C, warm undertone, never pure black),
rubbed/worn bronze-gold (#C9A24B with light/dark variation), and a single
sharp vermilion seal-red accent (#B23A2E) used sparingly. Surfaces evoke
xuan paper / parchment (#E8DCC0). Materials: paper grain, subtle ink-wash
edges, engraved metal, banner silhouettes. Chinese display type with brush/
carved character (e.g. Source Han Serif Heavy) for titles, clean sans for
data. Mood: solemn, weighty, martial, restrained negative space, light
emerging from darkness.

AVOID AI-slop: no Inter/Roboto/Arial, no purple-on-white gradients, no
generic rounded Bootstrap cards, no emoji icons, no cyber-neon, no pure black.
Make bold, intentional, context-specific choices. Think outside the box.
```

### 5B. 直播浮层 (最重要, 逐状态出图)

```
[风格锁] +

Design a small live-stream OVERLAY widget that floats over a Mount & Blade
battle, captured by OBS for viewers. 360x180px. Two-column: a martial icon
(troop type) on the left, command text on the right — large, high-contrast,
readable on a phone screen. Chinese text like "弓箭手 · 盾墙".

Deliver 4 STATES as separate frames:
1) Idle/listening — calm, a slow ink "breathing" glow
2) Recognizing — brief focused/thinking state
3) Executed (hero moment) — a vermilion seal (印章) stamps down with a quick
   scale-settle; show the troop + command boldly. THE delight moment.
4) Not-matched — quiet, low-key, non-intrusive

Background MUST be either transparent or a flat solid color (for OBS chroma
key) — no busy gradient behind. Keep it small, must not block the battlefield.
```

### 5C. 启动器 Hub / 配置界面

```
[风格锁] +

Design a desktop launcher panel (~460x520). A carved bronze title lockup with
the seal character "令", one primary action "开始语音指挥" as a weighty
bronze plate button, and 4 secondary tiles (测试模式/音频设置/指令词典/跑测试).
Use one hero focal point, generous negative space, engraved/embossed depth.
Show default and "running" states of the primary button.
```

---

## 6. 迭代技法 (一次出不好是正常的)

好设计靠**批判-修正循环**, 不是一次成:

1. **先要 3 个不同方向**: "give me 3 distinct art directions for this overlay"
   → 选最有感觉的一个继续深化。
2. **批判式追问**: "这版哪里显得像 AI 默认? 用上面的美术方向重做, 强化朱砂印章的高光时刻。"
3. **锁定风格再扩展**: 满意的那版, 把它的配色/字体/材质提炼成"风格锁", 后续每个界面都带上, 保证一致。
4. **给真实内容**, 别用占位符 —— "弓箭手·盾墙"比"Button/Label"能逼出更真实的排版。

---

## 7. 图 vs 代码: 两条路的差别

- **要"图"(Midjourney/图生成类)**: 重艺术方向、材质、参考、光影、构图; 加画质词; 一次一个状态。上面模板照用。
- **要"能落地的界面"(Claude 出 HTML/组件)**: 把 §5A 风格锁 + §4 负面清单当**系统提示**追加; 明确要 CSS 变量、Google Fonts、错峰入场动画。工程侧(我)可用 Tkinter 贴图还原静态稿, 或迁 Web 还原动效(见 product-design-brief.md 的路线 A/B)。

---

## 来源

- [Anthropic Cookbook — Prompting for frontend aesthetics](https://platform.claude.com/cookbook/coding-prompting-for-frontend-aesthetics)
- [GenDesigns — PROMPT framework for UI](https://gendesigns.ai/blog/ai-prompts-for-ui-design-complete-framework)
- [Prompt engineering for designers (Parallel HQ)](https://www.parallelhq.com/blog/prompt-engineering-designers)
