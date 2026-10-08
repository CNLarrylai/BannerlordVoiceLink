# 英文实战讲解视频 · 剪辑说明(2026-09-07 录制)

> 素材:`H:\2025录制\2026-09-07 12-43-18.mp4`(开篇口播 33 秒)+ `2026-09-07 12-25-27.mp4`(实战 6 分 04 秒)。
> 产物:`H:\2025录制\粗剪_语音指挥\语音指挥_粗剪_v1.mp4`(约 4 分 50 秒)+ 同名 `.srt`(改正后的英文字幕)+ `cutlist.json`。
> 剪映新版草稿(draft_content.json)是加密的,cutcli 也只能新建草稿、不能裁剪源片段,
> 所以走 ffmpeg 出粗剪 mp4 + SRT,你把这两个文件导进剪映做精修(转场/标题/BGM)。

## 一、总体评价

这条比 11:56 那条好很多:有一条真实的战斗主线,指令全部满分识别,顶部横幅每次都出现,
"新手朋友只会喊 attack them" 的故事是全片最好的一段。主要问题三个:

1. **旁白和指令混在一起说,指令被吞了四次**(shoot wall / gamish / 第一次 infantry attack them / 第一次 hold the high ground),
   每次都要重喊一遍,还说了一句 "Sorry, it's picking up my commands"。粗剪里全部剪掉了失败那次,只留成功那次。
2. **两处自己拆台**:"moving is usually easier with just your keyboard"(0:56-1:15)和
   "because I was explaining and giving commands at the same time, the AI wasn't picking it up"(2:28-2:41)。都剪了。
   诚实是好的,但结尾那段 "you can also do it with the keyboard, but voice gives immersion" 已经足够诚实,前面这两处只会让观众觉得工具不行。
3. **口播不流畅的段落**:"Right, this is pretty much of a..."(4:46-5:00)、"Okay I think we are doing pretty well" 后面十几秒空白。都剪了。

## 二、剪辑表(源时间 → 保留)

| # | 源 | 入点 | 出点 | 内容 | 备注 |
|---|---|---|---|---|---|
| 0 | 12-43-18 | 0:00.5 | 0:32.5 | 开篇口播 | 整段保留 |
| 1 | 12-25-27 | 0:01.5 | 0:12.5 | Let me show you… → Archers move in front → Archers split | 横幅 0:10 |
| 2 | | 0:12.8 | 0:22.0 | 分队解释 | |
| 3 | | 0:28.0 | 0:30.8 | All units, hold the high ground | 剪掉 0:22-0:28 失败的第一次 |
| 4 | | 0:31.5 | 0:56.0 | 键盘触发不了的原生 AI 指令 | 核心信息 |
| 5 | | 1:15.6 | 1:47.7 | Cavalry attack them + 新手朋友的故事 | 剪掉 0:56-1:15 "键盘更方便" |
| 6 | | 1:53.0 | 1:55.2 | They're fighting over here | 剪掉 1:48-1:53 "Sorry…" |
| 7 | | 1:57.8 | 2:01.5 | Infantry, attack them(成功的) | |
| 8 | | 2:01.8 | 2:28.6 | 敌骑射困高地 → 重排 group 2/5 → shield wall | |
| 9 | | 2:41.5 | 2:58.8 | 两队左右 → Horse archers follow me → 侧翼放箭 | 剪掉 2:28-2:41 道歉 |
| 10 | | 3:09.5 | 3:14.5 | Horse archers, skirmish(成功的) | 剪掉 gamish |
| 11 | | 3:14.8 | 3:21.5 | 送步兵 → Infantry charge | |
| 12 | | 3:26.5 | 3:46.5 | Infantry line → Cavalry charge! Yes | 剪掉重复的 charge |
| 13 | | 3:46.5 | 3:52.0 | 战斗留白 5 秒 | 给观众喘口气 |
| 14 | | 3:54.5 | 4:09.6 | 语音适合复杂指令 / 冲进去砍时不按键 | 核心信息 |
| 15 | | 4:32.5 | 4:46.5 | Horse archers attack infantry → 绕背 | 定向攻击第二次 |
| 16 | | 5:00.3 | 6:02.5 | 收尾 | 剪掉 4:46-5:00 |

## 三、字幕里改掉的说法

| 原话 | 字幕 |
|---|---|
| Man and Blade / modern blade player | Mount & Blade / new to Bannerlord |
| voice command mode | voice command mod |
| Infantry, shoot wall | Infantry, shield wall |
| fun for screamer | fun for streamers |
| it's for free and it's downloadable on Steam Workshop | It's free, and it's on the Steam Workshop |
| I have never built any mod by myself, but now thanks to the AI coding software | I have never built a mod by myself. But now, thanks to AI coding tools |
| you can attack in a specific troop | attacking a specific enemy formation |
| slay them first | finish them first |
| 句首 So / like / uh / um | 全删 |

## 四、建议补拍(按价值排序)

粗剪能直接发,但下面几条补上就是完整版。每条只需实况喊指令,旁白后期配或不配都行。

1. **分队后各自指挥**(30 秒)。现在只说了"一队左一队右",没做。
   喊:**"Archers, split."** → **"Group five, go to the right of the infantry."** → **"Archers left, fire at will."**
   这是"键盘做不到"的最直观画面,补拍插在剪辑表 #2 后面。
2. **定向攻击的对比一句话**(旁白,10 秒)。#15 的 "Horse archers, attack their infantry" 已经是定向攻击,
   但没解释它和原版的区别。补一句 VO:"In vanilla you have to hover the cursor on their formation first. Here I just say who to hit."
3. **绕后 flank**(20 秒)。**"Cavalry, flank!"** 骑兵绕大弯,画面最明显的战术层指令,一条都没出现。
4. **收回指挥**(10 秒)。托管战术后喊 **"Archers, halt."**,VO:"One direct order and they're back under my control. Nothing is handed to the AI."
   这是和 F6 托管的本质区别,现在片子里完全没提。
5. **稳步推进**(15 秒)。**"Infantry, advance carefully."** 只认这个说法。
6. **结尾卡**(5 秒,剪映里做)。Workshop 链接 + "Beta, unlisted, feedback welcome"。

## 五、注释特效(图例卡 + 当前指令卡)

产物都在 `H:\2025录制\粗剪_语音指挥\`:

| 文件 | 用途 |
|---|---|
| `语音指挥_粗剪_v1_注释预览.mp4` | ffmpeg 直接叠好的预览,看效果用;满意的话也可以直接当成片 |
| `注释卡PNG\legend.png` | 图例卡:五类指令 + 哪些是 F 键有的、哪些 mod only |
| `注释卡PNG\cmd00~11.png` | 指令卡:指令原文 + 类别徽章,每条指令一张 |
| `注释卡_时间表.csv` | 每张卡出现/消失的秒数和位置(按粗剪 v1 的时间轴) |
| `语音指挥_指令标注.srt` | 同样的信息做成字幕轨,不想摆 PNG 就直接导这个 |

**剪映里怎么放**(按时间表):
- 图例卡放画中画轨,位置左上(x=40,y=210),出现两次:开战头 11 秒、结尾总结那 24 秒。
- 指令卡放另一条画中画轨,位置左下(x=40,y=780),每条 3.5 秒;避开了游戏自己的左下战斗记录和右下摄像头。
- 五个类别的颜色固定:蓝=移动、绿=队形、橙=定向攻击、黄=分队与站位、红=AI 战术。橙黄红三类是 mod only。
- 想改字/改色:卡片由脚本生成,改 `CATS`/`EVENTS` 两张表重跑即可,不用手画。

## 六、交接流程:你剪 → 我叠卡 → 上传 YouTube

工具:`tools/annotate_video.py`(已用粗剪跑通,12/12 指令自动定位,零误报)。

**你在剪映里导出**(这是唯一一次有损导出,给足码率):
- 分辨率 1080p,帧率 60,格式 MP4,编码 H.264
- 码率选"更高"或自定义 ≥ 24 Mbps(剪映"推荐"档偏低,再经我一次重编码会糊)
- 音频默认 AAC 即可,我这边不重编音频,原样封装
- 不要在剪映里烧字幕,SRT 我单独给你,YouTube 上传时作为字幕轨传更好

**我这边一条命令**:
```
.venv\Scripts\python.exe tools\annotate_video.py "H:\...\成片.mp4"
```
- 自动转写、定位每条"兵种 + 指令"说完的时刻,卡在 0.15 秒后从右上角出现,停 3.5 秒
- 先出 `_注释时间表.csv` 和 `_注释核对.jpg` 给你确认;要改就改 csv,用 `--events` 重渲染
- 输出 `_注释版.mp4`:H.264 High,yuv420p,GOP 30,B 帧 2,NVENC cq19,1080p60 约 20 Mbps,moov 前置。YouTube 1080p60 推荐 12 Mbps,留了余量
- `--pos bottomleft` 可切到左下角;`--legend 33,43` 可加图例卡窗口

## 七、剪映精修建议

- 导入 mp4 后把 `.srt` 拖进字幕轨,字体用无衬线粗体,放在画面下方、摄像头画中画左侧,避免遮挡。
- 开篇口播(#0)和 #1 之间加一个 0.3 秒黑场或叠化;其它切点都是同一场战斗,硬切即可。
- 横幅出现的四个位置(0:10 move in front、1:20 attack them、2:30 shield wall、3:30 line)可以各放大 1 秒做特写。
- BGM 压到 -20dB 以下,你的口播是英文非母语,音乐一大就听不清。
