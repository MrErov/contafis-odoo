const { test, expect } = require('@playwright/test');
const { login, rpc, getActionId } = require('./helpers/odoo.js');

const PERIOD = '2026-06';
const PARTNER_RIF = 'J-31555555-5';
const PARTNER_NAME = 'E2E Planilla IVA';
const SALE_BASE = 2000;
const SALE_VAT = 320;
const PURCHASE_BASE = 1000;
const PURCHASE_VAT = 160;

async function cleanupPeriod(page) {
  const returns = await rpc(page, 'l10n.ve.vat.return', 'search_read',
    [[['period_month', '=', PERIOD]], ['id']],
    { limit: 100 }
  );
  if (returns.length) {
    await rpc(page, 'l10n.ve.vat.return', 'unlink', [returns.map((record) => record.id)]);
  }
  const lines = await rpc(page, 'l10n.ve.vat.book.line', 'search_read',
    [[['period_month', '=', PERIOD], ['invoice_number', 'like', 'E2E-']], ['id']],
    { limit: 100 }
  );
  if (lines.length) {
    await rpc(page, 'l10n.ve.vat.book.line', 'unlink', [lines.map((line) => line.id)]);
  }
}

async function ensurePartner(page) {
  const partners = await rpc(page, 'res.partner', 'search_read',
    [[['vat', '=', PARTNER_RIF]], ['id']],
    { limit: 1 }
  );
  return partners.length
    ? partners[0].id
    : rpc(page, 'res.partner', 'create', [{
        name: PARTNER_NAME,
        vat: PARTNER_RIF,
        supplier_rank: 1,
      }]);
}

async function readReturn(page) {
  const records = await rpc(page, 'l10n.ve.vat.return', 'search_read',
    [[['period_month', '=', PERIOD]], ['state', 'item_42', 'item_34']],
    { limit: 1 }
  );
  return records.length ? records[0] : { state: 'missing' };
}

test.describe('Planilla IVA 99030', () => {
  test.setTimeout(180000);

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('crear desde libro, calcular y exportar a Excel', async ({ page }) => {
    const users = await rpc(page, 'res.users', 'search_read',
      [[['login', '=', 'admin']], ['company_id']],
      { limit: 1 }
    );
    const companyId = users[0].company_id[0];

    await cleanupPeriod(page);
    const partnerId = await ensurePartner(page);

    const baseLine = {
      period_month: PERIOD,
      company_id: companyId,
      partner_id: partnerId,
      source: 'manual',
      retention_direction: 'to_vendor',
    };
    await rpc(page, 'l10n.ve.vat.book.line', 'create', [[
      {
        ...baseLine,
        book_type: 'sale',
        operation_code: '42',
        invoice_number: 'E2E-VTA-001',
        control_number: 'E2E-CTL-001',
        base_general: SALE_BASE,
        vat_general: SALE_VAT,
        total_with_vat: SALE_BASE + SALE_VAT,
      },
      {
        ...baseLine,
        book_type: 'purchase',
        operation_code: '33',
        invoice_number: 'E2E-CMP-001',
        control_number: 'E2E-CTL-002',
        base_general: PURCHASE_BASE,
        vat_general: PURCHASE_VAT,
        total_with_vat: PURCHASE_BASE + PURCHASE_VAT,
      },
    ]]);

    try {
      const actionId = await getActionId(page, 'l10n_ve_compliance_manager.action_l10n_ve_vat_return');
      await page.goto(`/odoo/action-${actionId}`, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.o_list_view, .o_control_panel', { timeout: 30000 });

      await page.click('.o_list_button_add');
      await page.waitForSelector('.o_form_view .o_field_widget[name="period_month"] input', { timeout: 15000 });
      await page.fill('.o_form_view .o_field_widget[name="period_month"] input', PERIOD);
      await page.click('.o_form_button_save');
      await page.waitForTimeout(1000);

      await expect.poll(async () => (await readReturn(page)).state, { timeout: 30000 }).toBe('draft');

      await page.click('button[name="action_load_from_book"]');
      await expect.poll(async () => (await readReturn(page)).state, { timeout: 30000 }).toBe('loaded');

      const loaded = await readReturn(page);
      expect(loaded.item_42).toBe(SALE_BASE);
      expect(loaded.item_34).toBe(PURCHASE_VAT);

      await expect(page.locator('.o_field_widget[name="item_49"]').first()).toContainText(String(SALE_VAT));
      await expect(page.locator('.o_field_widget[name="item_39"]').first()).toContainText(String(PURCHASE_VAT));
      await expect(page.locator('.o_field_widget[name="item_53"]').first()).toContainText(String(PURCHASE_VAT));

      await page.click('button[name="action_calculate"]');
      await expect.poll(async () => (await readReturn(page)).state, { timeout: 30000 }).toBe('calculated');

      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 30000 }),
        page.click('button[name="action_export_99030_xlsx"]'),
      ]);
      expect(download.suggestedFilename()).toContain(`Planilla_99030_${PERIOD}`);
    } finally {
      await cleanupPeriod(page).catch(() => {});
    }
  });
});
