// ==UserScript==
// @name         1688 → OZON 选品上架助手
// @namespace    ozon-erp
// @version      1.0.0
// @description  在 1688 商品详情页一键抓取商品信息，推送到 Ozon ERP 后台
// @author       Ozon ERP
// @match        https://detail.1688.com/offer/*
// @match        https://m.1688.com/offer/*
// @grant        GM_xmlhttpRequest
// @grant        GM_notification
// @connect      localhost
// @connect      127.0.0.1
// @connect      *
// ==/UserScript==

(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════
    // CONFIG — 修改为你的 ozon-erp 后端地址
    // ═══════════════════════════════════════════════════════
    const API_BASE = 'http://localhost:8000';
    const SOURCING_API = API_BASE + '/sourcing/api/import';

    // ═══════════════════════════════════════════════════════
    // SCRAPER — 从页面提取商品数据
    // ═══════════════════════════════════════════════════════

    function extractProductData() {
        const data = {
            source_url: window.location.href,
            title_cn: '',
            images_1688_urls: [],
            detail_images_1688_urls: [],
            skus: [],
            weight_kg: null,
            package_size: null,
            package_type_cn: null,
            material_cn: null,
            article_number: null,
            description_cn: null,
        };

        // ── 标题 ──────────────────────────────────────────
        const titleEl =
            document.querySelector('h1[data-testid="offer-title"]') ||
            document.querySelector('.offer-title') ||
            document.querySelector('h1') ||
            document.querySelector('[class*="title"]');
        if (titleEl) {
            data.title_cn = titleEl.textContent.trim();
        }

        // ── 主图 ──────────────────────────────────────────
        // 1688 商品轮播图区域
        const imgSelector = [
            '.image-viewer img',
            '.offer-image-viewer img',
            '[data-testid="offer-image"] img',
            '.detail-gallery img',
            '.offer-main-image',
            '.tab-content-container img',
        ].join(',');

        document.querySelectorAll(imgSelector).forEach((img) => {
            const src = img.src || img.getAttribute('data-src') || img.getAttribute('srcset')?.split(',')[0]?.trim()?.split(' ')[0];
            if (src && !src.includes('data:') && !src.includes('blank.gif')) {
                // 尝试获取高清图（替换尺寸参数）
                const hqSrc = src
                    .replace(/\d+x\d+\.(jpg|png|jpeg|webp)/, '.$1')
                    .replace(/_\d+x\d+/, '')
                    .replace(/\.webp\?.*/, '.jpg');
                if (!data.images_1688_urls.includes(hqSrc)) {
                    data.images_1688_urls.push(hqSrc);
                }
            }
        });

        // ── 详情图 ────────────────────────────────────────
        document.querySelectorAll('.detail-desc img, .description-content img, [data-module="detail-desc"] img').forEach((img) => {
            const src = img.src || img.getAttribute('data-src') || img.getAttribute('lazy-src');
            if (src && !src.includes('data:')) {
                data.detail_images_1688_urls.push(src);
            }
        });

        // ── SKU 价格 ──────────────────────────────────────
        const priceEls = document.querySelectorAll('[class*="price"] span, .price, .offer-price, [data-testid="price"]');
        let basePrice = null;
        for (const el of priceEls) {
            const text = el.textContent.trim();
            const match = text.match(/¥?\s*([\d.]+)\s*[-~]\s*¥?\s*([\d.]+)/);
            if (match) {
                basePrice = parseFloat(match[1]);
                break;
            }
        }
        if (!basePrice) {
            for (const el of priceEls) {
                const match = el.textContent.trim().match(/¥?\s*([\d.]+)/);
                if (match && parseFloat(match[1]) > 0.1) {
                    basePrice = parseFloat(match[1]);
                    break;
                }
            }
        }

        // ── SKU 规格 ──────────────────────────────────────
        const skuRows = document.querySelectorAll(
            '.sku-table tr, .sku-item, [class*="sku"] li, .prop-table tr, .offer-sku-item'
        );
        const skuMap = new Map();

        skuRows.forEach((row) => {
            const cells = row.querySelectorAll('td, span');
            const specText = Array.from(cells)
                .map((c) => c.textContent.trim())
                .filter(Boolean)
                .join(' ');
            const priceMatch = specText.match(/¥\s*([\d.]+)/);

            if (specText && specText.length > 2 && specText.length < 100) {
                // Group by spec text, dedup
                let match = priceMatch
                    ? { spec: specText.replace(/¥\s*[\d.]+/, '').trim(), price_cny: parseFloat(priceMatch[1]) }
                    : { spec: specText, price_cny: null };

                if (!skuMap.has(match.spec) || (match.price_cny && !skuMap.get(match.spec).price_cny)) {
                    if (!skuMap.has(match.spec)) {
                        skuMap.set(match.spec, match);
                    }
                }
            }
        });

        if (skuMap.size > 0) {
            data.skus = Array.from(skuMap.values());
        } else if (basePrice) {
            data.skus = [{ spec: '默认', price_cny: basePrice, moq: 2 }];
        }

        // ── 包装/参数信息 ──────────────────────────────────
        const paramRows = document.querySelectorAll(
            '.offer-attr-item, .prop-item, [class*="param"] tr, .attr-row, [data-testid="attribute"] tr'
        );
        paramRows.forEach((row) => {
            const label = (row.querySelector('.label, .attr-name, th, dt')?.textContent || '').trim().toLowerCase();
            const value = (row.querySelector('.value, .attr-value, td, dd')?.textContent || row.textContent).trim();

            if (label.includes('重量') || label.includes('净重') || label.includes('毛重')) {
                const kgMatch = value.match(/([\d.]+)\s*(kg|公斤|千克|г|g)/i);
                if (kgMatch) {
                    data.weight_kg = kgMatch[2].toLowerCase() === 'g' || kgMatch[2] === 'г'
                        ? parseFloat(kgMatch[1]) / 1000
                        : parseFloat(kgMatch[1]);
                }
            }
            if (label.includes('尺寸') || label.includes('规格') || label.includes('大小')) {
                const sizeMatch = value.match(/(\d+)\s*[×xX\*]\s*(\d+)\s*[×xX\*]?\s*(\d+)?/);
                if (sizeMatch) {
                    data.package_size = {
                        length_cm: parseFloat(sizeMatch[1]),
                        width_cm: parseFloat(sizeMatch[2]),
                        height_cm: sizeMatch[3] ? parseFloat(sizeMatch[3]) : 1,
                    };
                }
            }
            if (label.includes('包装') || label.includes('装箱') || label.includes('打包')) {
                data.package_type_cn = value;
            }
            if (label.includes('材质') || label.includes('面料') || label.includes('成分') || label.includes('材料')) {
                data.material_cn = value;
            }
            if (label.includes('货号') || label.includes('型号') || label.includes('编号') || label.includes('款号')) {
                data.article_number = value;
            }
            if (label.includes('描述') || label.includes('详情')) {
                data.description_cn = value;
            }
        });

        // ── 尝试从商品描述文本提取 ────────────────────────
        if (!data.description_cn) {
            const descEl = document.querySelector('[class*="description"], [class*="detail-intro"]');
            if (descEl) {
                data.description_cn = descEl.textContent.trim().substring(0, 2000);
            }
        }

        return data;
    }

    // ═══════════════════════════════════════════════════════
    // INJECT UI — 在页面底部添加操作按钮
    // ═══════════════════════════════════════════════════════

    function createPanel() {
        // Remove existing panel if any
        const existing = document.getElementById('ozon-sourcing-panel');
        if (existing) existing.remove();

        const panel = document.createElement('div');
        panel.id = 'ozon-sourcing-panel';
        panel.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 99999;
            background: white;
            border: 2px solid #2563eb;
            border-radius: 12px;
            padding: 16px;
            width: 320px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.2);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        `;

        panel.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <span style="font-weight:700;font-size:14px;color:#1e40af;">📤 推送到 OZON 上架</span>
                <button id="ozon-panel-close" style="background:none;border:none;cursor:pointer;font-size:18px;color:#999;">×</button>
            </div>
            <div id="ozon-preview" style="font-size:12px;color:#666;max-height:150px;overflow-y:auto;margin-bottom:12px;background:#f8fafc;border-radius:6px;padding:8px;line-height:1.5;">
                <div style="text-align:center;color:#999;">点击下方按钮抓取商品数据</div>
            </div>
            <div style="display:flex;gap:8px;">
                <button id="ozon-btn-scrape" style="
                    flex:1;background:#2563eb;color:white;border:none;
                    padding:10px 12px;border-radius:8px;font-size:13px;font-weight:600;
                    cursor:pointer;
                ">🔍 抓取数据</button>
                <button id="ozon-btn-send" style="
                    flex:1;background:#16a34a;color:white;border:none;
                    padding:10px 12px;border-radius:8px;font-size:13px;font-weight:600;
                    cursor:pointer;display:none;
                ">🚀 推送到后台</button>
            </div>
            <div id="ozon-status" style="font-size:11px;color:#999;margin-top:8px;text-align:center;"></div>
        `;

        document.body.appendChild(panel);

        // State
        let scrapedData = null;

        // Close button
        document.getElementById('ozon-panel-close').addEventListener('click', () => panel.remove());

        // Scrape button
        document.getElementById('ozon-btn-scrape').addEventListener('click', () => {
            const status = document.getElementById('ozon-status');
            status.textContent = '正在抓取...';
            status.style.color = '#f59e0b';

            try {
                scrapedData = extractProductData();
                const preview = document.getElementById('ozon-preview');
                preview.innerHTML =
                    `<div><strong>标题：</strong>${scrapedData.title_cn.substring(0, 40)}...</div>` +
                    `<div><strong>图片：</strong>${scrapedData.images_1688_urls.length} 张</div>` +
                    `<div><strong>SKU：</strong>${scrapedData.skus.length} 个</div>` +
                    `<div><strong>重量：</strong>${scrapedData.weight_kg ? scrapedData.weight_kg + 'kg' : '未识别'}</div>` +
                    `<div><strong>尺寸：</strong>${scrapedData.package_size ? JSON.stringify(scrapedData.package_size) : '未识别'}</div>` +
                    `<div><strong>材质：</strong>${scrapedData.material_cn || '未识别'}</div>` +
                    `<div><strong>包装：</strong>${scrapedData.package_type_cn || '未识别'}</div>`;

                document.getElementById('ozon-btn-send').style.display = 'block';
                status.textContent = '✅ 抓取完成，检查数据后点击推送';
                status.style.color = '#16a34a';
            } catch (e) {
                status.textContent = '❌ 抓取失败: ' + e.message;
                status.style.color = '#dc2626';
            }
        });

        // Send button
        document.getElementById('ozon-btn-send').addEventListener('click', () => {
            if (!scrapedData) return;

            const status = document.getElementById('ozon-status');
            status.textContent = '正在推送到 Ozon ERP...';
            status.style.color = '#f59e0b';

            // Use GM_xmlhttpRequest if available, fallback to fetch
            const send = (url, data) => {
                return fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
            };

            send(SOURCING_API, scrapedData)
                .then((res) => res.json())
                .then((json) => {
                    if (json.ok) {
                        status.innerHTML = `✅ 推送成功! <a href="${API_BASE}/sourcing/${json.record_id}" target="_blank" style="color:#2563eb;">打开后台查看</a>`;
                        status.style.color = '#16a34a';
                    } else {
                        status.textContent = '❌ 推送失败: ' + (json.error || '未知错误');
                        status.style.color = '#dc2626';
                    }
                })
                .catch((err) => {
                    // If fetch fails (CORS), try GM_xmlhttpRequest
                    if (typeof GM_xmlhttpRequest !== 'undefined') {
                        GM_xmlhttpRequest({
                            method: 'POST',
                            url: SOURCING_API,
                            headers: { 'Content-Type': 'application/json' },
                            data: JSON.stringify(scrapedData),
                            onload: function (res) {
                                try {
                                    const json = JSON.parse(res.responseText);
                                    if (json.ok) {
                                        status.innerHTML = `✅ 推送成功! <a href="${API_BASE}/sourcing/${json.record_id}" target="_blank" style="color:#2563eb;">打开后台查看</a>`;
                                        status.style.color = '#16a34a';
                                    } else {
                                        status.textContent = '❌ 推送失败: ' + (json.error || '');
                                        status.style.color = '#dc2626';
                                    }
                                } catch (e) {
                                    status.textContent = '❌ 解析响应失败';
                                    status.style.color = '#dc2626';
                                }
                            },
                            onerror: function () {
                                status.textContent = '❌ 连接后端失败，请确认 ozon-erp 已启动';
                                status.style.color = '#dc2626';
                            },
                        });
                    } else {
                        status.textContent = '❌ 连接失败，请确认后端已启动 (localhost:8000)';
                        status.style.color = '#dc2626';
                    }
                });
        });
    }

    // ═══════════════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════════════

    // Wait for page to load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(createPanel, 1500));
    } else {
        setTimeout(createPanel, 1500);
    }
})();
