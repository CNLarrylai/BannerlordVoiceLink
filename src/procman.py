# -*- coding: utf-8 -*-
"""进程管理 —— 一键清干净所有语音进程 + 让子进程随启动器一起退出。

解决"前台窗口关了、后台进程还在跑"两条路:
  1. stop_all(): 枚举并强杀所有本应用实例(打包版 BannerlordVoice.exe 或
     源码版 python/pythonw 跑 app.py), 可排除自己 —— 手动兜底, 保证清零。
  2. KillOnCloseJob: 启动器把每个拉起的子进程放进一个 Windows 作业对象,
     该对象设了 KILL_ON_JOB_CLOSE —— 启动器进程一消失(正常退出/被任务管理器
     结束/崩溃), 作业句柄关闭, 系统连带杀掉全部子进程。不再有孤儿。
"""
import ctypes
import os
import subprocess
from ctypes import wintypes

CREATE_NO_WINDOW = 0x08000000

# 枚举本应用的所有进程: 打包版按 exe 名; 源码版是 python 跑 app.py
_PS_LIST = (
    "Get-CimInstance Win32_Process -Filter "
    "\"Name='BannerlordVoice.exe' OR Name='pythonw.exe' OR Name='python.exe'\" | "
    "Where-Object { $_.Name -eq 'BannerlordVoice.exe' -or "
    "$_.CommandLine -match 'app\\.py' } | "
    "ForEach-Object { \"$($_.ProcessId)|$($_.Name)\" }"
)


def app_processes(exclude_pid=None):
    """返回 [(pid, name)] —— 正在跑的本应用进程 (自动排除当前进程与 exclude_pid)。"""
    skip = {os.getpid()}
    if exclude_pid:
        skip.add(int(exclude_pid))
    out = []
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", _PS_LIST],
                           capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            pid_s, name = line.split("|", 1)
            try:
                pid = int(pid_s)
            except ValueError:
                continue
            if pid in skip:
                continue
            out.append((pid, name))
    except Exception:
        pass
    return out


def stop_all(exclude_pid=None):
    """强杀所有本应用进程 (排除自己/exclude_pid)。返回杀掉的数量。"""
    procs = app_processes(exclude_pid)
    killed = 0
    for pid, _name in procs:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, creationflags=CREATE_NO_WINDOW)
            killed += 1
        except Exception:
            pass
    return killed


class KillOnCloseJob:
    """Windows 作业对象: 加入的进程会在本对象句柄关闭(即本进程退出)时被杀。

    失败即降级为无操作 —— 绝不能因为作业逻辑挂掉而挡住子进程启动。
    """

    def __init__(self):
        self.handle = None
        try:
            self.handle = self._create()
        except Exception:
            self.handle = None

    @staticmethod
    def _create():
        k32 = ctypes.windll.kernel32
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None

        class _BASIC(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IO(ctypes.Structure):
            _fields_ = [("ReadOperationCount", ctypes.c_uint64),
                        ("WriteOperationCount", ctypes.c_uint64),
                        ("OtherOperationCount", ctypes.c_uint64),
                        ("ReadTransferCount", ctypes.c_uint64),
                        ("WriteTransferCount", ctypes.c_uint64),
                        ("OtherTransferCount", ctypes.c_uint64)]

        class _EXT(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", _BASIC),
                        ("IoInfo", _IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info = _EXT()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        # JobObjectExtendedLimitInformation = 9
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info),
                                           ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return None
        return job

    def assign(self, pid):
        """把一个进程加入作业。失败静默(降级为普通子进程)。"""
        if not self.handle:
            return
        try:
            k32 = ctypes.windll.kernel32
            k32.OpenProcess.restype = wintypes.HANDLE
            # PROCESS_SET_QUOTA(0x100) | PROCESS_TERMINATE(0x1)
            h = k32.OpenProcess(0x0100 | 0x0001, False, int(pid))
            if h:
                k32.AssignProcessToJobObject(self.handle, h)
                k32.CloseHandle(h)
        except Exception:
            pass
