javascript:(async function(){
  try {
    var r = await fetch('/exploits/chain_loader.js', {cache:'no-store'});
    var t = await r.text();
    var v1 = t.indexOf('_earlySoftFallback') > -1;
    var v2 = t.indexOf('_injectFallbackBridge') > -1;
    var v3 = t.indexOf('SOFT-FALLBACK bridge IMMEDIATELY injected') > -1;
    console.log('=== chain_loader.js VERSION CHECK ===');
    console.log('HTTP status:', r.status);
    console.log('Content length:', t.length);
    console.log('Contains _earlySoftFallback:', v1);
    console.log('Contains _injectFallbackBridge:', v2);
    console.log('Contains SOFT-FALLBACK injected log:', v3);
    console.log('First 80 chars:', t.substring(0, 80));
    console.log('Lines around L33 (expected IIFE start):', t.split('\n').slice(30, 50).join('\n'));
    console.log('VERDICT:', (v1 && v2 && v3) ? 'NEW (SOFT-FALLBACK 已注入)' : 'OLD (服务器还是旧版, 需要重新上传)');
  } catch(e) {
    console.error('Fetch failed:', e);
  }
})();
