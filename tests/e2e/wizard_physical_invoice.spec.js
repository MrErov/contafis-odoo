const { test, expect } = require('@playwright/test');
const { login } = require('./helpers/odoo.js');

test.describe('Wizard Factura Física', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('se abre desde el menú', async ({ page }) => {
    // Navegar a la página principal
    await page.goto('/odoo/web', { waitUntil: 'domcontentloaded' });
    // Esperar a que el navbar esté visible (Odoo 19 necesita tiempo para cargar)
    await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 15000 });

    // Click en el botón Home Menu
    await page.locator('.o_navbar_apps_menu').first().click();
    await page.getByRole('menuitem', { name: 'Cumplimiento VE' }).click();
    await page.locator('.o_menu_sections button.dropdown-toggle:not(.d-none)').first().click();
    await page.getByRole('menuitem', { name: 'Factura Física Rápida' }).click();

    // Verificar que el wizard se abre (esperar título visible)
    await expect(page.getByText('Factura Física Rápida')).toBeVisible({ timeout: 15000 });
  });

  test('valida RIF inválido', async ({ page }) => {
    // Abrir wizard
    await page.goto('/odoo/web', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 15000 });
    await page.locator('.o_navbar_apps_menu').first().click();
    await page.getByRole('menuitem', { name: 'Cumplimiento VE' }).click();
    await page.locator('.o_menu_sections button.dropdown-toggle:not(.d-none)').first().click();
    await page.getByRole('menuitem', { name: 'Factura Física Rápida' }).click();

    // Esperar a que el título sea visible
    await expect(page.getByText('Factura Física Rápida')).toBeVisible({ timeout: 15000 });

    // Esperar a que el campo RIF esté visible y llenarlo
    const rifField = page.getByLabel('RIF?');
    await expect(rifField).toBeVisible({ timeout: 10000 });
    await rifField.fill('J-12345678-0');

    // Hacer blur para disparar onchange
    await page.keyboard.press('Tab');

    // Verificar que aparece error de RIF inválido
    await expect(page.locator('.o_notification, .modal:has-text("RIF inválido")')).toBeVisible({ timeout: 5000 });
  });

  test('crea factura de compra end-to-end', async ({ page }) => {
    // Abrir wizard
    await page.goto('/odoo/web', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 15000 });
    await page.locator('.o_navbar_apps_menu').first().click();
    await page.getByRole('menuitem', { name: 'Cumplimiento VE' }).click();
    await page.locator('.o_menu_sections button.dropdown-toggle:not(.d-none)').first().click();
    await page.getByRole('menuitem', { name: 'Factura Física Rápida' }).click();

    // Verificar que el wizard se abre
    await expect(page.getByText('Factura Física Rápida')).toBeVisible({ timeout: 15000 });

    // Llenar RIF válido (NO existe en DB → crea partner nuevo)
    const rifField = page.getByLabel('RIF?');
    await rifField.fill('J-31527189-4');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(800);

    // Llenar nombre del nuevo partner (requerido)
    const nameField = page.locator('.o_field_widget[name="new_partner_name"] input');
    if (await nameField.isVisible({ timeout: 2000 }).catch(() => false)) {
      await nameField.fill('Proveedor Test E2E');
    }

    // Llenar campos obligatorios
    await page.getByLabel('Número de Factura').fill('FAC-E2E-001');
    await page.getByLabel('Número de Control').fill('CTRL-E2E-001');
    await page.getByLabel('Base General 16%').fill('1000');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(500);

    // Submit
    await page.getByRole('button', { name: 'Crear y Postear' }).click();

    // Esperar un momento para que el submit procese
    await page.waitForTimeout(3000);

    // Verificar que NO hay notificación de error
    const errorNotification = page.locator('.o_notification.border-danger, .o_notification_content:has-text("error")');
    const hasError = await errorNotification.isVisible().catch(() => false);
    expect(hasError).toBe(false);

    // Verificar que el wizard se cerró (submit exitoso)
    await expect(page.locator('.o_dialog:has-text("Factura Física Rápida")')).not.toBeVisible({ timeout: 5000 });
  });
});
