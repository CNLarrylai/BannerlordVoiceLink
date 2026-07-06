# 测试套件 —— 可重复、可量化、可追踪

一句话: 每次改词典/键位/模型/参数后跑一下，**用数字确认有没有变好或变坏**。

## 一键运行

```
双击 run_tests.bat        （项目根目录）
# 或
python tests/run_all.py
python tests/run_all.py --skip-bench   # 只跑快的匹配回归
```

## 三个部分

| 文件 | 是什么 | 快慢 |
|---|---|---|
| `test_matcher.py` | 纯文本匹配回归（指令解析/聊天过滤/键序），**正确性硬门槛** | 秒级，不用显卡 |
| `bench_recognition.py` | 真实引擎跑语音语料，量化**命中率 + 延迟** | 需加载模型 |
| `corpus.yaml` | 黄金语料集（标注"这句话→该发什么键"），所有测试的标准答案 | — |

## 量化追踪

每次跑 `bench_recognition.py` 都会**追加一行**到 `results/history.csv`：

```
时间, 模型, 设备, 量化, 命令数, 命中, 命中率%, 聊天数, 误触, 延迟avg/p50/p95, 备注
```

这样能长期对比：换了模型命中率涨了没？改了词典延迟变了没？误触有没有增加？

## 对比不同配置

```
python tests/bench_recognition.py --model base   --note base基线
python tests/bench_recognition.py --model small  --note small对比
python tests/bench_recognition.py --device cpu --compute int8 --note 无显卡模拟
```

跑完看 `results/history.csv` 并排对比。

## 加测试用例

1. 往 `corpus.yaml` 加句子（命令写明期望 group/order；聊天只写 text）
2. 重新合成语音：`python tests/gen_corpus.py`
3. 匹配层的用例直接加在 `test_matcher.py` 的 SAMPLES/KEY_CASES 里

## 说明

- 语音用 Windows SAPI 中文 TTS（Huihui）合成，是**标准发音**，能筛出哪些词本身难识别；但不完全等于你真人的声音，真人某些口语/儿化音表现会不同。
- `audio/` 和 `results/` 是生成物，可随时用 `gen_corpus.py` 重建。
