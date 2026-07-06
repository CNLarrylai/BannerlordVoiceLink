"""一键跑全部测试: 匹配回归(快) + 识别基准(需模型)。

用法: python tests/run_all.py [--skip-bench]
  匹配回归失败 -> 非零退出 (这是硬性正确性门槛)。
  识别基准是量化追踪, 不作为失败门槛 (TTS 准确率非硬指标)。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(title, script, args=()):
    print("\n" + "=" * 56)
    print(f"▶ {title}")
    print("=" * 56)
    return subprocess.run([PY, os.path.join(HERE, script), *args]).returncode


def main():
    skip_bench = "--skip-bench" in sys.argv
    rc = run("匹配回归 (纯文本, 正确性门槛)", "test_matcher.py")
    if rc != 0:
        print("\n❌ 匹配回归有失败! 先修这个。")
        sys.exit(1)
    if skip_bench:
        print("\n✓ 匹配回归通过 (已跳过识别基准)。")
        return
    run("识别基准 (真实引擎, 命中率+延迟)", "bench_recognition.py")
    print("\n✓ 全部完成。识别历史见 tests/results/history.csv")


if __name__ == "__main__":
    main()
