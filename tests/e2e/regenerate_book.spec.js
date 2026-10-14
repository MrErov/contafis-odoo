const { test, expect } = require('@playwright/test');
const { login, getActionId, createTestVendorBill } = require('./helpers/odoo.js');

test.describe('Regenerar Libro', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('click en Regenerar Libro no tira error UI', async ({ page }) => {
    // Crear factura de proveedor via RPC (IDs dinámicos, no hardcodeados)
    const moveId = await createTestVendorBill(page);

    // Resolver action_id via XMLID estándar de Odoo
    const actionId = await getActionId(page, 'account.action_move_in_invoice_type');

    // Navegar al form view del move recién creado
    await page.goto(`/odoo/action-${actionId}/${moveId}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.o_form_view, [data-view="form"]', { timeout: 15000 });

    // ASSERT 1: el botón "Regenerar Libro" existe y es visible
    const regenButton = page.locator('button[name="action_regenerate_vat_book_line"]');
    await expect(regenButton).toBeVisible({ timeout: 10000 });

    // ASSERT 2: click no dispara notificación de error
    await regenButton.click();
    await page.waitForTimeout(3000);
    const errorNotif = page.locator('.o_notification.border-danger');
    await expect(errorNotif).not.toBeVisible({ timeout: 2000 });
  });
});
