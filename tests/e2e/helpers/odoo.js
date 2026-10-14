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

async function rpc(page, model, method, args, kwargs = {}) {
  const response = await page.request.post('/web/dataset/call_kw', {
    data: {
      jsonrpc: '2.0',
      method: 'call',
      params: { model, method, args, kwargs },
      id: Date.now(),
    },
  });
  if (!response.ok()) {
    throw new Error(`RPC HTTP ${response.status()}: ${await response.text()}`);
  }
  const json = await response.json();
  if (json.error) {
    const msg = json.error.data?.message || JSON.stringify(json.error);
    throw new Error(`RPC ${model}.${method} error: ${msg}`);
  }
  return json.result;
}

async function getActionId(page, xmlid) {
  const [module, name] = xmlid.split('.');
  const records = await rpc(page, 'ir.model.data', 'search_read',
    [[['module', '=', module], ['name', '=', name]], ['res_id']],
    { limit: 1 }
  );
  if (!records.length) {
    throw new Error(`XMLID ${xmlid} not found`);
  }
  return records[0].res_id;
}

async function createTestVendorBill(page, opts = {}) {
  const rif = opts.rif || 'J-77777777-7';
  const partnerName = opts.partnerName || 'Proveedor E2E Regenerate';
  const ref = opts.ref || `E2E-REGEN-${Date.now()}`;
  const amount = opts.amount || 100;

  // 1. Find or create partner
  const existing = await rpc(page, 'res.partner', 'search_read',
    [[['vat', '=', rif]], ['id']],
    { limit: 1 }
  );
  const partnerId = existing.length
    ? existing[0].id
    : await rpc(page, 'res.partner', 'create', [{
        name: partnerName,
        vat: rif,
        supplier_rank: 1,
      }]);

  // 2. Find purchase journal
  const journals = await rpc(page, 'account.journal', 'search_read',
    [[['type', '=', 'purchase']], ['id']],
    { limit: 1 }
  );
  if (!journals.length) throw new Error('No purchase journal found');

  // 3. Find expense account
  const accounts = await rpc(page, 'account.account', 'search_read',
    [[['account_type', '=', 'expense']], ['id']],
    { limit: 1 }
  );
  if (!accounts.length) throw new Error('No expense account found');

  // 4. Create bill
  const today = new Date().toISOString().slice(0, 10);
  const moveId = await rpc(page, 'account.move', 'create', [{
    move_type: 'in_invoice',
    partner_id: partnerId,
    journal_id: journals[0].id,
    invoice_date: today,
    ref: ref,
    invoice_line_ids: [[0, 0, {
      name: 'E2E regenerate test line',
      quantity: 1,
      price_unit: amount,
      account_id: accounts[0].id,
    }]],
  }]);

  // 5. Post it
  await rpc(page, 'account.move', 'action_post', [[moveId]]);

  return moveId;
}

async function cleanupTestPartner(page, rif) {
  const partners = await rpc(page, 'res.partner', 'search_read',
    [[['vat', '=', rif]], ['id']],
    { limit: 100 }
  );
  if (!partners.length) return;
  const partnerIds = partners.map(p => p.id);

  // 1. Reset posted moves to draft (unlink requires draft)
  const postedMoves = await rpc(page, 'account.move', 'search_read',
    [[['partner_id', 'in', partnerIds], ['state', '=', 'posted']], ['id']],
    { limit: 500 }
  );
  if (postedMoves.length) {
    await rpc(page, 'account.move', 'button_draft', [postedMoves.map(m => m.id)]);
  }

  // 2. Unlink all moves referencing the partner
  const allMoves = await rpc(page, 'account.move', 'search_read',
    [[['partner_id', 'in', partnerIds]], ['id']],
    { limit: 500 }
  );
  if (allMoves.length) {
    await rpc(page, 'account.move', 'unlink', [allMoves.map(m => m.id)]);
  }

  // 3. Unlink the partner
  await rpc(page, 'res.partner', 'unlink', [partnerIds]);
}

module.exports = {
  login,
  logout,
  ODOO_ADMIN,
  rpc,
  getActionId,
  createTestVendorBill,
  cleanupTestPartner,
};
