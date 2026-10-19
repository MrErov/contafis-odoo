const { test, expect } = require('@playwright/test');
const { login, logout, rpc, getActionId } = require('./helpers/odoo.js');

const COMPANY_B_NAME = 'E2E Compañía B';
const CLIENT_A = 'E2E Cliente A';
const CLIENT_B = 'E2E Cliente B';
const OBLIGATION_A = 'E2E Obligación A';
const OBLIGATION_B = 'E2E Obligación B';
const PARTNER_RIFS = ['J-31666666-6', 'J-31777777-7'];
const CLIENT_ACTION = 'l10n_ve_compliance_manager.action_l10n_ve_compliance_client';
const OBLIGATION_ACTION = 'l10n_ve_compliance_manager.action_l10n_ve_obligation';

async function getAdmin(page) {
  const users = await rpc(page, 'res.users', 'search_read',
    [[['login', '=', 'admin']], ['id', 'company_id']],
    { limit: 1 }
  );
  return users[0];
}

async function ensureCompanyB(page) {
  const found = await rpc(page, 'res.company', 'search_read',
    [[['name', '=', COMPANY_B_NAME]], ['id']],
    { limit: 1 }
  );
  return found.length
    ? found[0].id
    : rpc(page, 'res.company', 'create', [{ name: COMPANY_B_NAME }]);
}

async function ensureClient(page, name, companyId, rif, ctx) {
  const existing = await rpc(page, 'l10n.ve.compliance.client', 'search_read',
    [[['name', '=', name]], ['id']],
    { limit: 1, context: ctx }
  );
  if (existing.length) return existing[0].id;

  const partners = await rpc(page, 'res.partner', 'search_read',
    [[['vat', '=', rif]], ['id']],
    { limit: 1, context: ctx }
  );
  const partnerId = partners.length
    ? partners[0].id
    : await rpc(page, 'res.partner', 'create', [{ name: `${name} Partner`, vat: rif }], { context: ctx });

  return rpc(page, 'l10n.ve.compliance.client', 'create', [{
    name,
    partner_id: partnerId,
    company_id: companyId,
  }], { context: ctx });
}

async function ensureObligation(page, name, clientId, ctx) {
  const existing = await rpc(page, 'l10n.ve.obligation', 'search_read',
    [[['name', '=', name]], ['id']],
    { limit: 1, context: ctx }
  );
  if (existing.length) return existing[0].id;
  return rpc(page, 'l10n.ve.obligation', 'create', [{
    name,
    client_id: clientId,
  }], { context: ctx });
}

async function cleanupRecords(page, ctx) {
  const obligations = await rpc(page, 'l10n.ve.obligation', 'search_read',
    [[['name', 'in', [OBLIGATION_A, OBLIGATION_B]]], ['id']],
    { limit: 100, context: ctx }
  );
  if (obligations.length) {
    await rpc(page, 'l10n.ve.obligation', 'unlink', [obligations.map((record) => record.id)], { context: ctx });
  }
  const clients = await rpc(page, 'l10n.ve.compliance.client', 'search_read',
    [[['name', 'in', [CLIENT_A, CLIENT_B]]], ['id']],
    { limit: 100, context: ctx }
  );
  if (clients.length) {
    await rpc(page, 'l10n.ve.compliance.client', 'unlink', [clients.map((record) => record.id)], { context: ctx });
  }
  const partners = await rpc(page, 'res.partner', 'search_read',
    [[['vat', 'in', PARTNER_RIFS]], ['id']],
    { limit: 100, context: ctx }
  );
  if (partners.length) {
    await rpc(page, 'res.partner', 'unlink', [partners.map((record) => record.id)], { context: ctx });
  }
}

async function switchCompany(page, companyId, companyName) {
  await page.click('.o_switch_company_menu');
  const item = page.locator(`.o_switch_company_item[data-company-id="${companyId}"] .log_into`);
  await item.waitFor({ state: 'visible', timeout: 15000 });
  await item.click();
  await expect(page.locator('.o_switch_company_menu')).toContainText(companyName, { timeout: 30000 });
}

async function expectListShows(page, xmlid, visibleText, hiddenText) {
  const actionId = await getActionId(page, xmlid);
  await page.goto(`/odoo/action-${actionId}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.o_control_panel', { timeout: 30000 });
  const records = page.locator('.o_data_row, .o_kanban_record');
  await expect(records.filter({ hasText: visibleText })).toHaveCount(1, { timeout: 30000 });
  await expect(records.filter({ hasText: hiddenText })).toHaveCount(0, { timeout: 30000 });
}

test.describe('Aislamiento multi-compañía', () => {
  test.setTimeout(240000);

  test('clientes y obligaciones se aíslan según la compañía activa', async ({ page }) => {
    await login(page);

    const admin = await getAdmin(page);
    const companyAId = admin.company_id[0];
    const companyAName = admin.company_id[1];
    const companyBId = await ensureCompanyB(page);
    const ctx = { allowed_company_ids: [companyAId, companyBId] };

    await rpc(page, 'res.users', 'write', [[admin.id], { company_ids: [[4, companyBId]] }]);

    const clientAId = await ensureClient(page, CLIENT_A, companyAId, PARTNER_RIFS[0], ctx);
    const clientBId = await ensureClient(page, CLIENT_B, companyBId, PARTNER_RIFS[1], ctx);
    await ensureObligation(page, OBLIGATION_A, clientAId, ctx);
    await ensureObligation(page, OBLIGATION_B, clientBId, ctx);

    await logout(page);
    await login(page);

    try {
      await expectListShows(page, CLIENT_ACTION, CLIENT_A, CLIENT_B);
      await expectListShows(page, OBLIGATION_ACTION, OBLIGATION_A, OBLIGATION_B);

      await switchCompany(page, companyBId, COMPANY_B_NAME);

      await expectListShows(page, CLIENT_ACTION, CLIENT_B, CLIENT_A);
      await expectListShows(page, OBLIGATION_ACTION, OBLIGATION_B, OBLIGATION_A);

      await switchCompany(page, companyAId, companyAName);

      await expectListShows(page, CLIENT_ACTION, CLIENT_A, CLIENT_B);
      await expectListShows(page, OBLIGATION_ACTION, OBLIGATION_A, OBLIGATION_B);
    } finally {
      await cleanupRecords(page, ctx).catch(() => {});
    }
  });
});
