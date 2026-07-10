# 语音命令测试用例（模型无关 · 持续迭代）

> **这是所有识别引擎的统一标准答案。** KWS / Whisper / 未来任何模型都用这一套测，
> 结果才可比。改说法、加用例，只改这个文件 —— `kws/live_compare.py` 和基准脚本
> 直接解析下面的表格（三张表，管道符分列，命令用 commands.yaml 里的 key）。
>
> 期望列填 commands.yaml 里的 **key**（如 `to_position`），不是中文名。
> 想要一条命令多种说法，就多写几行、指向同一个 key。
>
> 用例更新记录：
> - 2026-07-08 建档；口语化改造（来这里/去那里、前进/慢慢推进、别动/停下、散开、打他们）。
> - 2026-07-09 按实战日志补高频说法：出击、回来、到这里、立定；组合补 全军出击、骑射冲锋。
>   （注意：改表会变动题号 → 旧录音按旧表存档，新一轮 live_compare 重录。）
> - 2026-07-09 口音基准（6声线TTS）：圆阵跨声线脆弱（元旦/圆润/人阵都差一截，且
>   元旦是日常词不能当别名）→ 补「围成圈」用例，作为圆阵的抗口音替代说法推荐。

## 兵种 groups

> ⚠️ 纯兵种对 Whisper 不公平（匹配层故意不响应"只有兵种没指令"），实战也不会
> 只喊兵种。保留仅供 KWS 单词识别能力参考，算总分时可另计。

| 说法 | group |
|---|---|
| 步兵 | infantry |
| 弓箭手 | archers |
| 骑兵 | cavalry |
| 骑射 | horse_archers |
| 全军 | all |

## 指令 orders（作用于当前选中编队）

| 说法 | order |
|---|---|
| 来这里 | to_position |
| 去那里 | to_position |
| 随我来 | follow_me |
| 冲锋 | charge |
| 前进 | advance |
| 慢慢推进 | advance |
| 打这只 | focus_target |
| 退后 | fall_back |
| 别动 | halt |
| 停下 | halt |
| 撤退 | retreat |
| 线阵 | line |
| 盾墙 | shield_wall |
| 散开 | loose |
| 圆阵 | circle |
| 方阵 | square |
| 三角阵 | skein |
| 排成一列 | column |
| 乱阵 | scatter |
| 自由射击 | fire_at_will |
| 停止射击 | hold_fire |
| 上马 | mount_toggle |
| 交给AI | ai_control |
| 朝向方向 | face_direction |
| 出击 | charge |
| 回来 | fall_back |
| 到这里 | to_position |
| 立定 | halt |
| 围成圈 | circle |

## 组合 combos（兵种 + 指令，最接近实战）

| 说法 | group | order |
|---|---|---|
| 骑兵冲锋 | cavalry | charge |
| 步兵盾墙 | infantry | shield_wall |
| 弓箭手散开 | archers | loose |
| 全军开战 | all | advance |
| 骑兵打他们 | cavalry | focus_target |
| 全军出击 | all | charge |
| 骑射冲锋 | horse_archers | charge |
