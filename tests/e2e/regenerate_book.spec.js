const { test, expect } = require('@playwright/test');
const { login } = require('./helpers/odoo.js');

test.describe('Regenerar Libro', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('click en Regenerar Libro no tira error UI', async ({ page }) => {
    // Usar factura creada via shell (ID 1137 = BILL/2026/10/0003)
    // Abrir directamente el form view de la factura
    await page.goto('/odoo/action-252/1137', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.o_form_view, [data-view="form"]', { timeout: 15000 });

    // ASSERT 1: el botón "Regenerar Libro" existe y es visible
    const regenButton = page.locator('button[name="action_regenerate_vat_book_line"]');
    await expect(regenButton).toBeVisible({ timeout: 10000 });

    // 2. Click en el botón
    await regenButton.click();
    await page.waitForTimeout(3000);

    // ASSERT 2: no hay notificación de error tras el click
    const errorNotif = page.locator('.o_notification.border-danger');
    await expect(errorNotif).not.toBeVisible({ timeout: 2000 });
  });
});
