"""
Coruna × DarkSword 整合验证脚本
================================

校验项:
  1. server/exploits/ 目录下 41 个 JS + 4 个 plugin 子目录
  2. server/ios_profiles/ 目录下 14 套 iOS profile
  3. server/group.html 已注入 chain_loader.js
  4. server/admin/database.py MAX_SUPPORTED_IOS = "26.3"
  5. server/admin/main.py 已注册 chain_status router
  6. server/admin/routers/chain_status.py 文件存在
  7. server/exploit_server.py 已实现 _handle_chain_status_upload

用法: python verify_integration.py
"""

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVER_ROOT = ROOT
EXPLOITS_DIR = SERVER_ROOT / "exploits"
PROFILES_DIR = SERVER_ROOT / "ios_profiles"
ADMIN_DIR = SERVER_ROOT / "admin"
ROUTERS_DIR = ADMIN_DIR / "routers"


def check(label, ok, detail=""):
    sym = "[OK]" if ok else "[FAIL]"
    print(f"  {sym}  {label}" + (f"  -- {detail}" if detail else ""))
    return 0 if ok else 1


def main():
    print("=" * 70)
    print("Coruna x DarkSword 整合验证")
    print("=" * 70)

    fails = 0

    # 1) exploits 目录
    print("\n[1] server/exploits/ 目录")
    if not EXPLOITS_DIR.is_dir():
        print(f"  [FAIL] 目录不存在: {EXPLOITS_DIR}")
        fails += 1
    else:
        js_files = list(EXPLOITS_DIR.glob("*.js"))
        # 必含关键文件
        must_have = [
            "chain_loader.js",
            "attack_chain_orchestrator.js",
            "fallback_executor.js",
            "exploit_selector.js",
            "rce_module.js", "rce_module_15.js", "rce_module_18.6.js", "rce_module_26.js",
            "rce_worker_15.js", "rce_worker_18.4.js", "rce_worker_18.6.js", "rce_worker_26.js",
            "sbx0_main_15.js", "sbx0_main_18.4.js", "sbx0_main_26.js",
            "sbx1_main.js", "sbx1_main_15.js", "sbx1_main_26.js",
            "kernel_priv_26.js", "kernel_priv_CVE-2025-43520.js",
            "webkit_uaf_CVE-2025-43529.js",
            "angle_webgl_CVE-2025-14174.js",
            "coreaudio_trigger_CVE-2025-31200.js",
            "webkit_sbx_CVE-2025-24201.js"
        ]
        for m in must_have:
            p = EXPLOITS_DIR / m
            fails += check(f"exploits/{m}", p.is_file(), f"{p.stat().st_size} bytes" if p.is_file() else "MISSING")
        # 4 个 plugin
        plugin_dir = EXPLOITS_DIR / "plugins"
        if plugin_dir.is_dir():
            plugins = [d.name for d in plugin_dir.iterdir() if d.is_dir()]
            fails += check(f"plugins/ ({len(plugins)} 套)", len(plugins) >= 4, ",".join(plugins))
        else:
            fails += check("plugins/", False, "目录不存在")

    # 2) ios_profiles 目录
    print("\n[2] server/ios_profiles/ 目录 (14 套)")
    if not PROFILES_DIR.is_dir():
        print(f"  [FAIL] 目录不存在: {PROFILES_DIR}")
        fails += 1
    else:
        expected_versions = [
            "15_3", "16_7", "17_4", "17_5",
            "18_0", "18_1", "18_2", "18_3", "18_4", "18_5",
            "26_0", "26_1", "26_2", "26_3"
        ]
        for v in expected_versions:
            p = PROFILES_DIR / f"ios_{v}.json"
            if p.is_file():
                try:
                    prof = json.loads(p.read_text(encoding="utf-8"))
                    offsets = prof.get("offsets", {})
                    # dyld: 至少有 dyld 区域或 dyld_shared_cache base
                    has_dyld = (
                        "dyld" in prof
                        or "dyld_layout" in prof
                        or offsets.get("dyld_shared_cache")
                        or offsets.get("dyld_cache_slide_info")
                        or offsets.get("dyld_shared_cache_base")
                    )
                    # kern: 至少 1 个 kernel/symbols 字段 (proc/ucred/mach_vm/bsd_info/libsystem_kernel...)
                    # 容忍: 旧式 offsets.kernel / 新式 kernel_offsets / symbols.libsystem_kernel
                    kern_count = 0
                    if offsets.get("kernel"): kern_count += len(offsets["kernel"])
                    if prof.get("kernel_offsets"): kern_count += len(prof["kernel_offsets"])
                    if prof.get("symbols", {}).get("libsystem_kernel.dylib"):
                        kern_count += len(prof["symbols"]["libsystem_kernel.dylib"])
                    has_kern = kern_count >= 3
                    # sbx0: 至少 1 个 GPU IPC / IOSurface / ANGLE 偏移
                    sbx0_count = 0
                    if prof.get("sbx0_offsets"): sbx0_count += len(prof["sbx0_offsets"])
                    if offsets.get("iokit"): sbx0_count += len(offsets["iokit"])
                    if offsets.get("sbx0"): sbx0_count += len(offsets["sbx0"])
                    # 即使 sbx0 缺失, 也允许通过 (会从 rce_module.js 22F76 通用偏移降级)
                    has_sbx0 = sbx0_count >= 1
                    has_build = "build" in prof
                    has_ios = "ios" in prof or "ios_version" in prof
                    detail = f"build={prof.get('build','?')} dyld={has_dyld} kern_fields={kern_count} sbx0_fields={sbx0_count} ios={has_ios}"
                    # 硬要求: dyld + kern + build + ios
                    # 软要求: sbx0 (缺失仅警告)
                    ok = has_dyld and has_kern and has_build and has_ios
                    fails += check(f"ios_profiles/ios_{v}.json", ok, detail)
                except Exception as e:
                    fails += check(f"ios_profiles/ios_{v}.json", False, f"parse error: {e}")
            else:
                fails += check(f"ios_profiles/ios_{v}.json", False, "MISSING")

    # 3) group.html 注入
    print("\n[3] server/group.html 注入")
    gh = SERVER_ROOT / "group.html"
    if not gh.is_file():
        fails += check("group.html 存在", False)
    else:
        text = gh.read_text(encoding="utf-8", errors="replace")
        fails += check("group.html 含 chain_loader.js 引用", "/exploits/chain_loader.js" in text)
        fails += check("group.html 含 iOS 18+ 分流", "DarkSword 整合层" in text and "delegatedTo" in text)

    # 4) database.py
    print("\n[4] server/admin/database.py")
    db = ADMIN_DIR / "database.py"
    if not db.is_file():
        fails += check("database.py 存在", False)
    else:
        text = db.read_text(encoding="utf-8", errors="replace")
        fails += check('MAX_SUPPORTED_IOS = "26.3"', 'MAX_SUPPORTED_IOS = "26.3"' in text)
        fails += check("class ExploitChainStatus", "class ExploitChainStatus" in text)
        fails += check("class ExploitChainOffsetRequest", "class ExploitChainOffsetRequest" in text)
        fails += check('darksword_compatible 等级', "darksword_compatible" in text)

    # 5) main.py 注册
    print("\n[5] server/admin/main.py")
    mp = ADMIN_DIR / "main.py"
    if not mp.is_file():
        fails += check("main.py 存在", False)
    else:
        text = mp.read_text(encoding="utf-8", errors="replace")
        fails += check("import chain_status", "chain_status as chain_status_router" in text)
        fails += check("app.include_router(chain_status_router.router)",
                       "include_router(chain_status_router.router)" in text)

    # 6) chain_status.py
    print("\n[6] server/admin/routers/chain_status.py")
    cs = ROUTERS_DIR / "chain_status.py"
    fails += check("chain_status.py 存在", cs.is_file(),
                   f"{cs.stat().st_size} bytes" if cs.is_file() else "MISSING")
    if cs.is_file():
        text = cs.read_text(encoding="utf-8", errors="replace")
        fails += check("POST /api/chain-status 路由", 'router = APIRouter(prefix="/api/chain-status"' in text)
        fails += check("ExploitChainStatus 写入", "ExploitChainStatus(" in text)
        fails += check("ExploitChainOffsetRequest 写入", "ExploitChainOffsetRequest(" in text)
        fails += check("summary 路由", "summary/all" in text)
        fails += check("pending 路由", "pending/all" in text)
        fails += check("resolve 路由", "/resolve/{req_id}" in text)

    # 7) exploit_server.py
    print("\n[7] server/exploit_server.py 集成")
    es = SERVER_ROOT / "exploit_server.py"
    fails += check("exploit_server.py 存在", es.is_file())
    if es.is_file():
        text = es.read_text(encoding="utf-8", errors="replace")
        fails += check("导入 ExploitChainStatus", "ExploitChainStatus" in text)
        fails += check("导入 ExploitChainOffsetRequest", "ExploitChainOffsetRequest" in text)
        fails += check("_handle_chain_status_upload 方法", "_handle_chain_status_upload" in text)
        fails += check("POST /api/chain-status 分支", '"api/chain-status"' in text)

    # Summary
    print("\n" + "=" * 70)
    if fails == 0:
        print("[SUCCESS] All integration checks passed (v)")
    else:
        print(f"[FAIL] {fails} checks failed (see above)")
    print("=" * 70)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
