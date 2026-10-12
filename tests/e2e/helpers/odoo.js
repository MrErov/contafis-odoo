const ODOO_ADMIN = {
  login: process.env.ODOO_USER || 'admin',
  password: process.env.ODOO_PASSWORD || 'admin',
};

async function login(page) {
  await page.goto('/web/login');
  await page.fill('input[name="login"]', ODOO_ADMIN.login);
  await page.fill('input[name="password"]', ODOO_ADMIN.password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/odoo|\/web#/, { timeout: 15000 });
  await page.waitForLoadState('networkidle');
}

async function logout(page) {
  await page.goto('/web/session/logout');
}

module.exports = { login, logout, ODOO_ADMIN };
