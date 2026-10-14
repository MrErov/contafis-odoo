const path = require('path');
const fs = require('fs');
const { chromium } = require('@playwright/test');

const ODOO_URL = process.env.ODOO_URL || 'http://localhost:8090';
const USER = process.env.ODOO_USER || 'admin';
const PASS = process.env.ODOO_PASSWORD || 'admin';
const OUT_DIR = path.join(__dirname, '..', 'docs', 'guia-usuario', 'assets', 'screenshots');

async function login(page) {
  await page.goto(`${ODOO_URL}/web/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="login"]', USER);
  await page.fill('input[name="password"]', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/odoo|\/web#/, { timeout: 30000 });
  await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 30000 });
}

async function injectAnnotations(page, annotations) {
  await page.evaluate((anns) => {
    const old = document.getElementById('__guide_overlay__');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.id = '__guide_overlay__';
    overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
    document.body.appendChild(overlay);

    for (const a of anns) {
      const el = document.querySelector(a.selector);
      if (!el) {
        console.warn(`  ⚠ Selector not found: ${a.selector}`);
        continue;
      }
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const rect = el.getBoundingClientRect();

      if (a.type === 'box' || !a.type) {
        const box = document.createElement('div');
        box.style.cssText = `
          position: fixed;
          left: ${rect.left - 4}px;
          top: ${rect.top - 4}px;
          width: ${rect.width + 8}px;
          height: ${rect.height + 8}px;
          border: 3px solid #e63946;
          border-radius: 4px;
          box-shadow: 0 0 0 2px rgba(255,255,255,0.9);
          box-sizing: border-box;
        `;
        overlay.appendChild(box);
      }

      if (a.label) {
        const badge = document.createElement('div');
        badge.textContent = a.label;
        badge.style.cssText = `
          position: fixed;
          left: ${rect.left - 18}px;
          top: ${rect.top - 18}px;
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: #e63946;
          color: white;
          font-weight: bold;
          font-family: sans-serif;
          font-size: 17px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          border: 2px solid white;
          box-sizing: border-box;
        `;
        overlay.appendChild(badge);
      }
    }
  }, annotations);
}

async function clearAnnotations(page) {
  await page.evaluate(() => {
    const o = document.getElementById('__guide_overlay__');
    if (o) o.remove();
  });
}

async function capture(page, spec) {
  const outPath = path.join(OUT_DIR, `${spec.name}.png`);
  if (fs.existsSync(outPath) && !process.env.FORCE) {
    console.log(`↻ ${spec.name}.png (exists, skip; FORCE=1 to overwrite)`);
    return;
  }

  console.log(`→ ${spec.name}`);
  await page.goto(`${ODOO_URL}${spec.url}`, { waitUntil: 'domcontentloaded' });
  if (spec.waitFor) {
    await page.waitForSelector(spec.waitFor, { timeout: 20000 });
  }
  if (spec.beforeCapture) {
    await spec.beforeCapture(page);
  }
  await page.waitForTimeout(600);
  if (spec.annotations && spec.annotations.length) {
    await injectAnnotations(page, spec.annotations);
  }
  await page.waitForTimeout(400);
  await page.screenshot({
    path: outPath,
    fullPage: spec.fullPage === true,
  });
  await clearAnnotations(page);
  console.log(`  ✓ saved ${path.relative(process.cwd(), outPath)}`);
}

// === SPECS ===
// Cada screenshot que necesita la guía. Agregar entradas a medida
// que se escriban más secciones.

const specs = [
  {
    name: '02-01-login',
    url: '/web/login',
    waitFor: 'input[name="login"]',
    annotations: [
      { selector: 'input[name="login"]', label: '1' },
      { selector: 'input[name="password"]', label: '2' },
      { selector: 'button[type="submit"]', label: '3' },
    ],
  },
  {
    name: '02-02-company-form',
    url: '/odoo/action-base.action_res_company_form/1',
    waitFor: '.o_form_view',
    annotations: [
      { selector: '.o_field_widget[name="vat"]', label: '1' },
      { selector: '.o_field_widget[name="name"]', label: '2' },
    ],
  },
  {
    name: '02-03-user-prefs',
    url: '/odoo/action-base.action_res_users_my',
    waitFor: '.o_form_view',
    annotations: [
      { selector: '.o_field_widget[name="lang"]', label: '1' },
      { selector: '.o_field_widget[name="tz"]', label: '2' },
    ],
  },
  {
    name: '02-04-apps-module',
    url: '/odoo/apps',
    waitFor: '.o_list_view, .o_kanban_view',
    annotations: [],
  },
  {
    name: '02-05-smtp',
    url: '/odoo/action-base.action_ir_mail_server_list?debug=1',
    waitFor: '.o_list_view, .o_form_view, .o_content',
    annotations: [],
  },
  {
    name: '03-01-client-form',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client',
    waitFor: '.o_list_view, .o_kanban_view',
    beforeCapture: async (page) => {
      const newBtn = page.locator(
        'button.o_list_button_add, button.o-kanban-button-new, .o_control_panel button:has-text("Nuevo")'
      ).first();
      await newBtn.click();
      await page.waitForSelector('.o_form_view', { timeout: 15000 });
    },
    annotations: [
      { selector: '.o_field_widget[name="name"]', label: '1' },
      { selector: '.o_field_widget[name="rif"]', label: '2' },
    ],
  },
  {
    name: '03-02-client-list',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '03-03-client-kanban',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client?view_type=kanban',
    waitFor: '.o_kanban_view',
    annotations: [],
  },
  {
    name: '04-01-wizard-open',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '04-02-operation-type',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [
      { selector: '.o_field_widget[name="type"]', label: '1' },
    ],
  },
  {
    name: '04-03-rif-new-partner',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    beforeCapture: async (page) => {
      const rif = page.locator('input[name="partner_vat"], .o_field_widget[name="partner_vat"] input').first();
      await rif.fill('J-99999999-9');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(1500);
    },
    annotations: [],
  },
  {
    name: '04-04-emission-type',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [
      { selector: '.o_field_widget[name="emission_type"]', label: '1' },
    ],
  },
  {
    name: '04-05-machine-fields',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    beforeCapture: async (page) => {
      const widget = page.locator('.o_field_widget[name="emission_type"]').first();
      const nativeSelect = widget.locator('select');
      const hasNative = (await nativeSelect.count()) > 0;
      if (hasNative) {
        await nativeSelect.selectOption('maquina_fiscal');
      } else {
        await widget.locator('.o_input, button').first().click();
        await page.waitForTimeout(400);
        await page
          .locator('.dropdown-menu .dropdown-item, .o-dropdown--menu .dropdown-item, li.dropdown-item')
          .filter({ hasText: /máquina|maquina|Máquina|Maquina/ })
          .first()
          .click();
      }
      await page.waitForTimeout(1000);
    },
    annotations: [],
  },
  {
    name: '04-06-bases-iva',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    beforeCapture: async (page) => {
      const base16 = page.locator('.o_field_widget[name="base_general"] input').first();
      await base16.fill('1000');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(800);
    },
    annotations: [],
  },
  {
    name: '05-01-book-generate',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_book_generate',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '05-02-book-list',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_book_line?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '05-03-book-import',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_import_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '05-04-book-export',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_book_export_wizard',
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '06-01-planilla-generate',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_return',
    waitFor: '.o_list_view, .o_kanban_view',
    beforeCapture: async (page) => {
      const newBtn = page.locator('button.o_list_button_add, button.o-kanban-button-new, .o_control_panel button:has-text("Nuevo")').first();
      if (await newBtn.count() > 0) {
        await newBtn.click();
        await page.waitForSelector('.o_form_view', { timeout: 15000 });
      }
    },
    annotations: [],
  },
  {
    name: '06-02-planilla-form',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_return?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '06-03-planilla-export',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_return?view_type=list',
    waitFor: '.o_list_view, .o_control_panel',
    annotations: [
      { selector: '.o_list_button_add', label: '1' },
    ],
  },

];

// === MAIN ===

(async () => {
  if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  try {
    await login(page);
    console.log('✓ login OK');
    for (const spec of specs) {
      try {
        await capture(page, spec);
      } catch (err) {
        console.error(`  ✗ ${spec.name} failed: ${err.message}`);
      }
    }
  } finally {
    await browser.close();
  }

  console.log(`\n✓ Done. Screenshots in ${path.relative(process.cwd(), OUT_DIR)}`);
})().catch(err => { console.error(err); process.exit(1); });
