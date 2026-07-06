"""机器指纹 —— 稳定的本机标识, 供将来授权绑定/限制装机数用。

现在没人用它做限制; 只是先把能力备好。用 Windows MachineGuid(稳定、
重装软件不变), 取不到时退回网卡地址。返回 16 位短哈希, 不暴露原始信息。
"""
import hashlib


def machine_id() -> str:
    raw = None
    try:
        import winreg

        k = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        )
        raw, _ = winreg.QueryValueEx(k, "MachineGuid")
        winreg.CloseKey(k)
    except Exception:
        try:
            import uuid

            raw = str(uuid.getnode())
        except Exception:
            raw = "unknown"
    return hashlib.sha256(str(raw).encode()).hexdigest()[:16]


if __name__ == "__main__":
    print("machine id:", machine_id())
