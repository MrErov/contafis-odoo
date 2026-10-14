const { test, expect } = require('@playwright/test');
const { login, getActionId, createTestVendorBill, cleanupTestPartner } = require('./helpers/odoo.js');

test.describe('Regenerar Libro', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('click en Regenerar Libro no tira error UI', async ({ page }) => {
    const rif = 'J-77777777-7';
    let moveId;
    try {
      moveId = await createTestVendorBill(page, { rif });
      const actionId = await getActionId(page, 'account.action_move_in_invoice_type');
      await page.goto(`/odoo/action-${actionId}/${moveId}`, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.o_form_view, [data-view="form"]', { timeout: 15000 });

      const regenButton = page.locator('button[name="action_regenerate_vat_book_line"]');
      await expect(regenButton).toBeVisible({ timeout: 10000 });

      await regenButton.click();
      await page.waitForTimeout(3000);
      const errorNotif = page.locator('.o_notification.border-danger');
      await expect(errorNotif).not.toBeVisible({ timeout: 2000 });
    } finally {
      await cleanupTestPartner(page, rif).catch(() => {});
    }
  });
});
