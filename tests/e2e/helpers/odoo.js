const ODOO_ADMIN = {
  login: process.env.ODOO_USER || 'admin',
  password: process.env.ODOO_PASSWORD || 'admin',
};

async function login(page) {
  await page.goto('/web/login');
  await page.fill('input[name="login"]', ODOO_ADMIN.login);
  await page.fill('input[name="password"]', ODOO_ADMIN.password);
  await page.click('button[type="submit"]');
  // Wait for redirect to main page - look for the main menu or user avatar
  await page.waitForURL(/\/odoo|\/web#/, { timeout: 30000 });
  // Wait for the main navigation to appear (more reliable than networkidle for Odoo)
  await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 30000 });
}

async function logout(page) {
  await page.goto('/web/session/logout');
}

module.exports = { login, logout, ODOO_ADMIN };
