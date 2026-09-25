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
    rc = run("重试助推/回声抑制 (纯逻辑, 正确性门槛)", "test_retry.py")
    if rc != 0:
        print("\n❌ 重试助推测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("伴侣模组桥 (假服务器, 正确性门槛)", "test_modlink.py")
    if rc != 0:
        print("\n❌ modlink 测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("配置版本迁移 (打包版升级, 正确性门槛)", "test_config_migrate.py")
    if rc != 0:
        print("\n❌ 配置迁移测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("指令树校验 (词典键位对照物, 正确性门槛)", "test_order_tree.py")
    if rc != 0:
        print("\n❌ 指令树校验有失败! 先修这个。")
        sys.exit(1)
    rc = run("CUDA库检测下载 (GPU按需, 正确性门槛)", "test_cuda_libs.py")
    if rc != 0:
        print("\n❌ CUDA库测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("识别退化过滤 (重复幻觉, 正确性门槛)", "test_stt_filter.py")
    if rc != 0:
        print("\n❌ 退化过滤测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("模型下载 (测速择优/续传换源/校验, 正确性门槛)", "test_models_download.py")
    if rc != 0:
        print("\n❌ 模型下载源测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("监听门 (手动开关/战斗自动门, 正确性门槛)", "test_gate.py")
    if rc != 0:
        print("\n❌ 监听门测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("监听键轻点判定 (Alt+Tab/按住不算, 正确性门槛)", "test_hotkeys.py")
    if rc != 0:
        print("\n❌ 监听键测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("编队名册 (真实兵种成分选队/缺队拒发, 正确性门槛)", "test_roster.py")
    if rc != 0:
        print("\n❌ 编队名册测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("校准/个人词典 (发音适配, 正确性门槛)", "test_calibrate.py")
    if rc != 0:
        print("\n❌ 校准测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("指令复盘 (说法提取/usage兼容, 正确性门槛)", "test_review.py")
    if rc != 0:
        print("\n❌ 指令复盘测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("语音数据共建 (采集/导出/归集, 正确性门槛)", "test_donation.py")
    if rc != 0:
        print("\n❌ 数据共建测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("相对站位解析 (A去B的C[D], 正确性门槛)", "test_relpos.py")
    if rc != 0:
        print("\n❌ 相对站位测试有失败! 先修这个。")
        sys.exit(1)
    rc = run("整活词典 (激活/合并/路由, 正确性门槛)", "test_fun_pack.py")
    if rc != 0:
        print("\n❌ 整活词典测试有失败! 先修这个。")
        sys.exit(1)
    if skip_bench:
        print("\n✓ 匹配回归通过 (已跳过识别基准)。")
        return
    run("识别基准 (真实引擎, 命中率+延迟)", "bench_recognition.py")
    run("识别基准·英文 (真实引擎, Zira+David)", "bench_recognition.py", ["--lang", "en"])
    print("\n✓ 全部完成。识别历史见 tests/results/history.csv")


if __name__ == "__main__":
    main()
