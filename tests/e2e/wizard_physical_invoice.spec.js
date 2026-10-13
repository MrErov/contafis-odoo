const { test, expect } = require('@playwright/test');
const { login } = require('./helpers/odoo.js');

test.describe('Wizard Factura Física', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('se abre desde el menú', async ({ page }) => {
    // Navegar a la página principal
    await page.goto('/odoo/web', { waitUntil: 'domcontentloaded' });

    // Click en el botón Home Menu
    await page.getByTitle('Home Menu').first().click();
    await page.getByRole('menuitem', { name: 'Cumplimiento VE' }).click();
    await page.getByTitle('More Menu').first().click();
    await page.getByRole('menuitem', { name: 'Factura Física Rápida' }).click();

    // Verificar que el wizard se abre (esperar título visible)
    await expect(page.getByText('Factura Física Rápida')).toBeVisible({ timeout: 15000 });
  });

  test('valida RIF inválido', async ({ page }) => {
    // Abrir wizard
    await page.goto('/odoo/web', { waitUntil: 'domcontentloaded' });
    await page.getByTitle('Home Menu').first().click();
    await page.getByRole('menuitem', { name: 'Cumplimiento VE' }).click();
    await page.getByTitle('More Menu').first().click();
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
    await page.getByTitle('Home Menu').first().click();
    await page.getByRole('menuitem', { name: 'Cumplimiento VE' }).click();
    await page.getByTitle('More Menu').first().click();
    await page.getByRole('menuitem', { name: 'Factura Física Rápida' }).click();

    // Esperar a que el wizard se abra
    await expect(page.getByText('Factura Física Rápida')).toBeVisible({ timeout: 15000 });

    // Rellenar datos - RIF válido existente
    const rifField = page.getByLabel('RIF?');
    await expect(rifField).toBeVisible({ timeout: 10000 });
    await rifField.fill('J-31527189-4');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(1000); // esperar onchange

    // Llenar campos obligatorios
    const invoiceNumberField = page.getByLabel('Número de Factura');
    await expect(invoiceNumberField).toBeVisible({ timeout: 10000 });
    await invoiceNumberField.fill('FAC-E2E-001');

    const controlNumberField = page.getByLabel('Número de Control');
    await expect(controlNumberField).toBeVisible({ timeout: 10000 });
    await controlNumberField.fill('CTRL-E2E-001');

    const baseGeneralField = page.getByLabel('Base General 16%');
    await expect(baseGeneralField).toBeVisible({ timeout: 10000 });
    await baseGeneralField.fill('1000');
    await baseGeneralField.press('Tab');
    await page.waitForTimeout(3000); // esperar cálculo de IVA (onchange puede ser lento)

    // Verificar que IVA General se calcula (16% de 1000 = 160)
    // Buscar el valor 160 cerca de "IVA General 16%" en el dialog
    await expect(page.locator('.o_dialog')).toContainText('160', { timeout: 10000 });

// Para fecha de emisión, click en el botón del datepicker y seleccionar día 15
    await page.getByRole('button', { name: 'Fecha de Emisión' }).first().click();
    // Esperar a que el datepicker se abra
    await page.waitForTimeout(1000);
    // Seleccionar día 15 - usar selector más genérico para la celda del datepicker
    await page.locator('button:has-text("15"), span:has-text("15"), div:has-text("15"), [role="gridcell"]:has-text("15")').first().click({ timeout: 10000 });
    await page.waitForTimeout(500);

    // Llenar campos de nuevo partner (requeridos si el RIF no existe en BD)
    const newPartnerNameField = page.getByLabel('Razón Social');
    if (await newPartnerNameField.isVisible({ timeout: 2000 }).catch(() => false)) {
      await newPartnerNameField.fill('Proveedor Test E2E');
      // El campo "Tipo" para nuevo partner es un input que abre un dropdown al hacer click
      const newPartnerTypeField = page.getByLabel('Tipo', { exact: true }).locator('..').locator('input[id*="new_partner_type"]');
      await newPartnerTypeField.click();
      // Esperar a que se abra el dropdown y seleccionar la primera opción
      await page.waitForTimeout(500);
      // Usar selector más genérico para el dropdown dentro del dialog
      await page.locator('.o_dialog >> a, .o_dialog button, .o_dialog [role="menuitem"]').first().click({ timeout: 5000 });
    }

    // Click "Crear y Postear"
    await page.getByRole('button', { name: 'Crear y Postear' }).click();
    // Esperar a que la acción complete (redirección o error)
    await page.waitForTimeout(3000);

    // Verificar si hay errores de validación
    const errorNotification = page.locator('.o_notification.error, .alert-danger, .o_notification:has-text("Error")');
    if (await errorNotification.isVisible({ timeout: 2000 }).catch(() => false)) {
      const errorText = await errorNotification.textContent();
      throw new Error(`Error de validación: ${errorText}`);
    }

    // Verificar redirección a account.move
    await expect(page).toHaveURL(/\/odoo\/account\.move\/\d+/, { timeout: 15000 });

    // Verificar que aparece botón "Regenerar Libro" en la factura posteada
    await expect(page.getByRole('button', { name: /Regenerar Libro/i })).toBeVisible({ timeout: 10000 });
  });
});
