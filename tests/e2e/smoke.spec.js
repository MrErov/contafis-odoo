const { test, expect } = require('@playwright/test');
const { login } = require('./helpers/odoo.js');

test.describe('Smoke — Login + navegación básica', () => {
  test('admin puede hacer login', async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL(/\/odoo/);
    await expect(page.locator('header')).toBeVisible();
  });

  test('navbar principal visible con elementos de menú', async ({ page }) => {
    await login(page);
    // Verificar que el navbar principal existe y tiene elementos clickeables
    const navbar = page.locator('.o_main_navbar, .o_menu_navbar, nav, .oe_topbar_menu');
    await expect(navbar.first()).toBeVisible({ timeout: 10000 });

    // Verificar que hay al menos un elemento de menú clickeable
    const menuItems = page.locator('.o_menu_item, .o_menu_text, .dropdown-toggle, .o_menu_brand');
    const count = await menuItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test('no hay errores JS en consola', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(err.message));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await login(page);
    // Esperar a que el navbar principal esté visible (en lugar de networkidle)
    await page.waitForSelector('.o_main_navbar, header', { timeout: 30000 });
    await page.waitForTimeout(2000);

    const realErrors = errors.filter(
      (e) => !e.toLowerCase().includes('label') &&
             !e.toLowerCase().includes('accessibility') &&
             !e.toLowerCase().includes('title')
    );
    expect(realErrors).toEqual([]);
  });
});
