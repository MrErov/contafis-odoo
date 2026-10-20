const path = require('path');
const fs = require('fs');
const { chromium } = require('@playwright/test');

const ODOO_URL = process.env.ODOO_URL || 'http://localhost:8090';
const USER = process.env.ODOO_USER || 'admin';
const PASS = process.env.ODOO_PASSWORD || 'admin';
const OUT_DIR = path.join(__dirname, '..', 'docs', 'guia-usuario', 'assets', 'screenshots');

const APP_URL = '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client?view_type=kanban';

// Abre un wizard como diálogo SOBRE la app Cumplimiento VE. Navegar
// directamente a la acción del wizard deja de fondo la app por defecto
// del usuario (Conversaciones), por eso primero se carga una vista de
// Cumplimiento VE y luego se dispara el wizard de forma client-side.
// Devuelve false si el wizard requiere un registro (activeIdModel) que
// todavía no existe en la base de datos.
async function openWizard(page, actionXmlid, opts = {}) {
  const appUrl = opts.appUrl || APP_URL;
  const appWaitFor = opts.appWaitFor || '.o_kanban_view';
  await page.goto(`${ODOO_URL}${appUrl}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector(appWaitFor, { timeout: 20000 });
  const result = await page.evaluate(async ({ xmlid, model }) => {
    const env = window.odoo.__WOWL_DEBUG__.root.env;
    let additionalContext;
    if (model) {
      const ids = await env.services.orm.search(model, [], { limit: 1 });
      if (!ids.length) return { skipped: true };
      additionalContext = { active_id: ids[0] };
    }
    await env.services.action.doAction(xmlid, additionalContext ? { additionalContext } : {});
    return { ok: true };
  }, { xmlid: actionXmlid, model: opts.activeIdModel });
  await page.waitForTimeout(800);
  return !result.skipped;
}

async function login(page) {
  await page.goto(`${ODOO_URL}/web/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="login"]', USER);
  await page.fill('input[name="password"]', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/odoo|\/web#/, { timeout: 30000 });
  await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 30000 });
}

async function logout(page) {
  await page.goto(`${ODOO_URL}/web/session/logout`, { waitUntil: 'domcontentloaded' });
}

// JSON-RPC desde Node: comparte cookies con el navegador y es inmune al
// reload del webclient que disparan las escrituras de companias/usuarios.
async function rpc(page, model, method, args, kwargs = {}) {
  const response = await page.request.post(`${ODOO_URL}/web/dataset/call_kw`, {
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
    const msg = (json.error.data && json.error.data.message) || JSON.stringify(json.error);
    throw new Error(`RPC ${model}.${method}: ${msg}`);
  }
  return json.result;
}

// Habilita TODAS las companias del usuario en la sesion. La seleccion
// multi-compania activa vive en la cookie `cids` (ids ordenados unidos
// por "-"): sin ella, una sesion fresca solo permite company_id y los
// RPCs/vistas ocultan clientes y documentos de las demas companias.
async function enableAllCompanies(page) {
  const admins = await rpc(page, 'res.users', 'search_read',
    [[['login', '=', 'admin']], ['id', 'company_ids']], { limit: 1 });
  if (!admins.length) return;
  const ids = admins[0].company_ids.slice().sort((a, b) => a - b);
  if (!ids.length) return;
  await page.context().addCookies([{
    name: 'cids',
    value: ids.join('-'),
    url: ODOO_URL,
  }]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.o_main_navbar, .o_user_menu, header', { timeout: 30000 });
  console.log(`\u2713 companias activas via cids=${ids.join('-')}`);
}

// Seed multi-compania (idempotente): cada cliente vive en su propia
// compania, el admin las ve todas y existe un usuario contador demo.
// Va por JSON-RPC porque crear companias / escribir en el propio usuario
// admin dispara un reload del webclient que destruiria un page.evaluate.
async function seedMultiCompany(page) {
  const stats = { companies: 0, users: 0 };

  const ensureCompany = async (name) => {
    const found = await rpc(page, 'res.company', 'search_read',
      [[['name', '=', name]], ['id']], { limit: 1 });
    if (found.length) return found[0].id;
    stats.companies += 1;
    return rpc(page, 'res.company', 'create', [{ name }]);
  };
  const companyB = await ensureCompany('Servicios Andinos, S.A.');
  const companyC = await ensureCompany('Inversiones Maracaibo, C.A.');

  const setClientCompany = async (name, companyId) => {
    const found = await rpc(page, 'l10n.ve.compliance.client', 'search_read',
      [[['name', '=', name]], ['id']], { limit: 1 });
    if (found.length) {
      await rpc(page, 'l10n.ve.compliance.client', 'write',
        [[found[0].id], { company_id: companyId }]);
    }
  };
  await setClientCompany('Servicios Andinos, S.A.', companyB);
  await setClientCompany('Inversiones Maracaibo, C.A.', companyC);

  const admins = await rpc(page, 'res.users', 'search_read',
    [[['login', '=', 'admin']], ['id', 'company_id']], { limit: 1 });
  if (admins.length) {
    await rpc(page, 'res.users', 'write',
      [[admins[0].id], { company_ids: [[4, companyB], [4, companyC]] }]);
  }
  const companyId = admins.length ? admins[0].company_id[0] : null;

  const xmlidResId = async (xmlid) => {
    const [module, name] = xmlid.split('.');
    const recs = await rpc(page, 'ir.model.data', 'search_read',
      [[['module', '=', module], ['name', '=', name]], ['res_id']], { limit: 1 });
    return recs.length ? recs[0].res_id : null;
  };
  const groups = [];
  for (const xmlid of [
    'base.group_user',
    'base.group_multi_company',
    'l10n_ve_compliance_manager.l10n_ve_compliance_accountant',
    'account.group_account_manager',
  ]) {
    const gid = await xmlidResId(xmlid);
    if (gid) groups.push(gid);
  }

  const users = await rpc(page, 'res.users', 'search_read',
    [[['login', '=', 'contador.demo']], ['id']], { limit: 1 });
  if (!users.length) {
    stats.users += 1;
    await rpc(page, 'res.users', 'create', [{
      name: 'María Rodríguez',
      login: 'contador.demo',
      password: 'demo',
      company_id: companyId,
      company_ids: [[6, 0, [companyId, companyB, companyC].filter(Boolean)]],
      group_ids: [[6, 0, groups]],
    }]);
  }

  console.log(
    `\u2713 seed multi-compania: ${stats.companies} companias nuevas, `
    + `${stats.users} usuarios nuevos (RPC)`,
  );
}

// Siembra data demo reproducible (idempotente) para que los screenshots de
// listas/formularios no salgan vacA-os. No borra nada: busca por nombre y
// crea solo lo que falta. Desactivar con SKIP_SEED=1.
async function seedDemoData(page) {
  const admins = await rpc(page, 'res.users', 'search_read',
    [[['login', '=', 'admin']], ['id', 'company_id']], { limit: 1 });
  const adminCompanyId = admins.length ? admins[0].company_id[0] : null;
  const result = await page.evaluate(async ({ adminCompanyId }) => {
    const env = window.odoo.__WOWL_DEBUG__.root.env;
    const orm = env.services.orm;
    const call = (model, method, args = [], kwargs = {}) => orm.call(model, method, args, kwargs);
    const stats = { partners: 0, clients: 0, documents: 0, statuses: 0, returns: 0, alerts: 0, obligations: 0 };

    let companyId = adminCompanyId;
    if (!companyId && env.services.company && env.services.company.currentCompany) {
      companyId = env.services.company.currentCompany.id;
    }

    const seedPartner = async (name, rif, phone) => {
      const found = await orm.search('res.partner', [['name', '=', name]], { limit: 1 });
      if (found.length) return found[0];
      stats.partners += 1;
      return call('res.partner', 'create', [{
        name,
        is_company: true,
        company_type: 'company',
        vat: rif,
        phone,
      }]);
    };

    const seedClient = async (name, rif, activity, municipality) => {
      const found = await orm.search('l10n.ve.compliance.client', [['name', '=', name]], { limit: 1 });
      if (found.length) return found[0];
      const partnerId = await seedPartner(name, rif, '+58 414-0000000');
      stats.clients += 1;
      return call('l10n.ve.compliance.client', 'create', [{
        name,
        partner_id: partnerId,
        company_id: companyId,
        rif,
        activity_type: activity,
        municipality,
      }]);
    };

    const clientA = await seedClient('Distribuidora El Sol, C.A.', 'J-40123456-7', 'comercio', 'Libertador');
    const clientB = await seedClient('Servicios Andinos, S.A.', 'J-40987654-3', 'servicios', 'Baruta');
    const clientC = await seedClient('Inversiones Maracaibo, C.A.', 'J-31555666-9', 'mixto', 'Maracaibo');

    const docTypes = await orm.search(
      'l10n.ve.document.type',
      [['required_for', '=', 'company']],
      { limit: 6, order: 'code' },
    );

    const seedDocument = async (clientId, docTypeId, number, issueDate, expiryDate, state) => {
      const found = await orm.search('l10n.ve.document', [
        ['client_id', '=', clientId],
        ['document_type_id', '=', docTypeId],
        ['number', '=', number],
      ], { limit: 1 });
      if (found.length) return;
      stats.documents += 1;
      await call('l10n.ve.document', 'create', [{
        client_id: clientId,
        document_type_id: docTypeId,
        number,
        issue_date: issueDate,
        expiry_date: expiryDate,
        state,
      }]);
    };

    if (docTypes.length) {
      await seedDocument(clientA, docTypes[0], 'DOC-A-001', '2026-01-15', '2026-12-31', 'valid');
      await seedDocument(clientA, docTypes[1] || docTypes[0], 'DOC-A-002', '2026-02-01', '2026-11-30', 'valid');
      await seedDocument(clientA, docTypes[2] || docTypes[0], 'DOC-A-003', '2025-03-01', '2025-12-31', 'expired');
      await seedDocument(clientB, docTypes[0], 'DOC-B-001', '2026-03-10', '2026-12-15', 'valid');
    }

    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1);

    const seedSnapshot = async (clientId) => {
      const found = await orm.search('l10n.ve.cartelera.status', [
        ['client_id', '=', clientId],
        ['year', '=', year],
        ['month', '=', month],
      ], { limit: 1 });
      if (found.length) return;
      const created = await call('l10n.ve.cartelera.status', 'generate_snapshot', [clientId, year, month]);
      stats.statuses += Array.isArray(created) ? created.length : 1;
    };
    await seedSnapshot(clientA);
    await seedSnapshot(clientB);
    await seedSnapshot(clientC);

    const seedReturn = async (periodMonth, vals) => {
      const found = await orm.search('l10n.ve.vat.return', [
        ['period_month', '=', periodMonth],
        ['company_id', '=', companyId],
      ], { limit: 1 });
      let id;
      if (found.length) {
        id = found[0];
        await call('l10n.ve.vat.return', 'write', [[id], vals]);
      } else {
        stats.returns += 1;
        id = await call('l10n.ve.vat.return', 'create', [{ period_month: periodMonth, company_id: companyId, ...vals }]);
      }
      await call('l10n.ve.vat.return', 'action_calculate', [[id]]);
    };
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const prev2 = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    await seedReturn(fmt(prev), { item_42: 15000.0, item_43: 2400.0, item_33: 9000.0, item_34: 1440.0 });
    await seedReturn(fmt(prev2), { item_42: 8000.0, item_43: 1280.0, item_33: 14000.0, item_34: 2240.0 });

    const seedAlert = async (clientId, alertType, state) => {
      const name = `Alerta demo ${alertType} ${clientId}`;
      const found = await orm.search('l10n.ve.alert', [['name', '=', name]], { limit: 1 });
      if (found.length) return;
      stats.alerts += 1;
      await call('l10n.ve.alert', 'create', [{
        name,
        client_id: clientId,
        alert_type: alertType,
        state,
        channel: 'email',
        date: new Date().toISOString().slice(0, 19).replace('T', ' '),
      }]);
    };
    await seedAlert(clientA, 'overdue', 'pending');
    await seedAlert(clientA, 'due_soon', 'pending');
    await seedAlert(clientB, 'document_expiring', 'sent');
    await seedAlert(clientC, 'missing_payment', 'done');

    const islrTypes = await orm.search('l10n.ve.obligation.type', [
      ['seniat_table_code', 'in', ['est_islr', 'ret_islr']],
    ]);
    if (islrTypes.length) {
      for (const clientId of [clientA, clientB, clientC]) {
        await call('l10n.ve.compliance.client', 'write', [[clientId], {
          applicable_type_ids: [[6, 0, islrTypes]],
        }]);
      }
      for (const clientId of [clientA, clientB, clientC]) {
        const action = await call('l10n.ve.compliance.client', 'action_generate_obligations', [[clientId]]);
        const message = (action && action.params && action.params.message) || '';
        const match = /generaron (\d+)/.exec(message);
        stats.obligations += match ? Number(match[1]) : 0;
      }
    }

    return stats;
  }, { adminCompanyId });
  console.log(
    `\u2713 seed demo: ${result.partners} partners, ${result.clients} clients, `
    + `${result.documents} docs, ${result.statuses} snapshots, `
    + `${result.returns} planillas, ${result.alerts} alertas, `
    + `${result.obligations} obligaciones`,
  );
  await seedMultiCompany(page);
}

async function injectAnnotations(page, annotations) {
  await page.evaluate((anns) => {
    const old = document.getElementById('__guide_overlay__');
    if (old) old.remove();

    const overlay = document.createElement('div');
    overlay.id = '__guide_overlay__';
    overlay.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
    document.body.appendChild(overlay);

    for (const a of anns) {
      const el = document.querySelector(a.selector);
      if (!el) {
        console.warn(`  ⚠ Selector not found: ${a.selector}`);
        continue;
      }
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const rect = el.getBoundingClientRect();

      if (a.type === 'box' || !a.type) {
        const box = document.createElement('div');
        box.style.cssText = `
          position: fixed;
          left: ${rect.left - 4}px;
          top: ${rect.top - 4}px;
          width: ${rect.width + 8}px;
          height: ${rect.height + 8}px;
          border: 3px solid #e63946;
          border-radius: 4px;
          box-shadow: 0 0 0 2px rgba(255,255,255,0.9);
          box-sizing: border-box;
        `;
        overlay.appendChild(box);
      }

      if (a.label) {
        const badge = document.createElement('div');
        badge.textContent = a.label;
        badge.style.cssText = `
          position: fixed;
          left: ${rect.left - 18}px;
          top: ${rect.top - 18}px;
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: #e63946;
          color: white;
          font-weight: bold;
          font-family: sans-serif;
          font-size: 17px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          border: 2px solid white;
          box-sizing: border-box;
        `;
        overlay.appendChild(badge);
      }
    }
  }, annotations);
}

async function clearAnnotations(page) {
  await page.evaluate(() => {
    const o = document.getElementById('__guide_overlay__');
    if (o) o.remove();
  });
}

async function capture(page, spec) {
  const outPath = path.join(OUT_DIR, `${spec.name}.png`);
  if (fs.existsSync(outPath) && !process.env.FORCE) {
    console.log(`↻ ${spec.name}.png (exists, skip; FORCE=1 to overwrite)`);
    return;
  }

  console.log(`→ ${spec.name}`);
  if (spec.beforeGoto) {
    const ok = await spec.beforeGoto(page);
    if (ok === false) {
      console.log(`  ⚠ ${spec.name} omitido: falta data (registro requerido inexistente)`);
      return;
    }
  } else {
    await page.goto(`${ODOO_URL}${spec.url}`, { waitUntil: 'domcontentloaded' });
  }
  if (spec.waitFor) {
    await page.waitForSelector(spec.waitFor, { timeout: 20000 });
  }
  if (spec.beforeCapture) {
    await spec.beforeCapture(page);
  }
  await page.waitForTimeout(600);
  if (spec.annotations && spec.annotations.length) {
    await injectAnnotations(page, spec.annotations);
  }
  await page.waitForTimeout(400);
  await page.screenshot({
    path: outPath,
    fullPage: spec.fullPage === true,
  });
  await clearAnnotations(page);
  console.log(`  ✓ saved ${path.relative(process.cwd(), outPath)}`);
}

// === SPECS ===
// Cada screenshot que necesita la guía. Agregar entradas a medida
// que se escriban más secciones.

const specs = [
  {
    name: '02-01-login',
    url: '/web/login',
    waitFor: 'input[name="login"]',
    annotations: [
      { selector: 'input[name="login"]', label: '1' },
      { selector: 'input[name="password"]', label: '2' },
      { selector: 'button[type="submit"]', label: '3' },
    ],
  },
  {
    name: '02-02-company-form',
    url: '/odoo/action-base.action_res_company_form/1',
    waitFor: '.o_form_view',
    annotations: [
      { selector: '.o_field_widget[name="vat"]', label: '1' },
      { selector: '.o_field_widget[name="name"]', label: '2' },
    ],
  },
  {
    name: '02-03-user-prefs',
    url: '/odoo/action-base.action_res_users_my',
    waitFor: '.o_form_view',
    annotations: [
      { selector: '.o_field_widget[name="lang"]', label: '1' },
      { selector: '.o_field_widget[name="tz"]', label: '2' },
    ],
  },
  {
    name: '02-04-apps-module',
    url: '/odoo/apps',
    waitFor: '.o_list_view, .o_kanban_view',
    annotations: [],
  },
  {
    name: '02-05-smtp',
    url: '/odoo/action-base.action_ir_mail_server_list?debug=1',
    waitFor: '.o_list_view, .o_form_view, .o_content',
    annotations: [],
  },
  {
    name: '02-06-companies-list',
    url: '/odoo/action-base.action_res_company_form?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '02-07-user-access',
    beforeGoto: async (page) => {
      const users = await rpc(page, 'res.users', 'search_read',
        [[['login', '=', 'contador.demo']], ['id']], { limit: 1 });
      if (!users.length) return false;
      await page.goto(`${ODOO_URL}/odoo/action-base.action_res_users/${users[0].id}`, {
        waitUntil: 'domcontentloaded',
      });
      return true;
    },
    waitFor: '.o_form_view',
    annotations: [
      { selector: '.o_field_widget[name="company_ids"]', label: '1' },
      { selector: '.o_field_widget[name="group_ids"]', label: '2' },
    ],
  },
  {
    name: '03-01-client-form',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client',
    waitFor: '.o_list_view, .o_kanban_view',
    beforeCapture: async (page) => {
      const newBtn = page.locator(
        'button.o_list_button_add, button.o-kanban-button-new, .o_control_panel button:has-text("Nuevo")'
      ).first();
      await newBtn.click();
      await page.waitForSelector('.o_form_view', { timeout: 15000 });
    },
    annotations: [
      { selector: '.o_field_widget[name="name"]', label: '1' },
      { selector: '.o_field_widget[name="rif"]', label: '2' },
    ],
  },
  {
    name: '03-02-client-list',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '03-03-client-kanban',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client?view_type=kanban',
    waitFor: '.o_kanban_view',
    annotations: [],
  },
  {
    name: '03-04-company-switcher',
    url: APP_URL,
    waitFor: '.o_kanban_view',
    beforeCapture: async (page) => {
      await page
        .locator('.o_switch_company_menu .dropdown-toggle, .o_switch_company_menu button')
        .first()
        .click();
      await page.waitForSelector('.o_switch_company_item', { timeout: 10000 });
      await page.waitForTimeout(400);
    },
    annotations: [],
  },
  {
    name: '04-01-wizard-open',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '04-02-operation-type',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [
      { selector: '.o_field_widget[name="type"]', label: '1' },
    ],
  },
  {
    name: '04-03-rif-new-partner',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    beforeCapture: async (page) => {
      const rif = page.locator('input[name="partner_vat"], .o_field_widget[name="partner_vat"] input').first();
      await rif.fill('J-99999999-9');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(1500);
    },
    annotations: [],
  },
  {
    name: '04-04-emission-type',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [
      { selector: '.o_field_widget[name="emission_type"]', label: '1' },
    ],
  },
  {
    name: '04-05-machine-fields',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    beforeCapture: async (page) => {
      const widget = page.locator('.o_field_widget[name="emission_type"]').first();
      const nativeSelect = widget.locator('select');
      const hasNative = (await nativeSelect.count()) > 0;
      if (hasNative) {
        await nativeSelect.selectOption('maquina_fiscal');
      } else {
        await widget.locator('.o_input, button').first().click();
        await page.waitForTimeout(400);
        await page
          .locator('.dropdown-menu .dropdown-item, .o-dropdown--menu .dropdown-item, li.dropdown-item')
          .filter({ hasText: /máquina|maquina|Máquina|Maquina/ })
          .first()
          .click();
      }
      await page.waitForTimeout(1000);
    },
    annotations: [],
  },
  {
    name: '04-06-bases-iva',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_physical_invoice_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    beforeCapture: async (page) => {
      const base16 = page.locator('.o_field_widget[name="base_general"] input').first();
      await base16.fill('1000');
      await page.keyboard.press('Tab');
      await page.waitForTimeout(800);
    },
    annotations: [],
  },
  {
    name: '05-01-book-generate',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_vat_book_generate'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '05-02-book-list',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_book_line?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '05-03-book-import',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_import_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '05-04-book-export',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_vat_book_export_wizard'),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '06-01-planilla-generate',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_return',
    waitFor: '.o_list_view, .o_kanban_view',
    beforeCapture: async (page) => {
      const newBtn = page.locator('button.o_list_button_add, button.o-kanban-button-new, .o_control_panel button:has-text("Nuevo")').first();
      if (await newBtn.count() > 0) {
        await newBtn.click();
        await page.waitForSelector('.o_form_view', { timeout: 15000 });
      }
    },
    annotations: [],
  },
  {
    name: '06-02-planilla-form',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_return?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '06-03-planilla-export',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_vat_return?view_type=list',
    waitFor: '.o_list_view, .o_control_panel',
    annotations: [
      { selector: '.o_list_button_add', label: '1' },
    ],
  },
  {
    name: '08-01-calendario-tablas',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_seniat_calendar?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '08-02-calendario-tabla-form',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_seniat_calendar?view_type=list',
    waitFor: '.o_list_view',
    beforeCapture: async (page) => {
      await page.locator('.o_list_view .o_data_row').first().click();
      await page.waitForSelector('.o_form_view', { timeout: 15000 });
    },
    annotations: [],
  },
  {
    name: '08-03-feriados-bancarios',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_bank_holiday?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '08-04-cliente-config-fiscal',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_compliance_client?view_type=list',
    waitFor: '.o_list_view',
    beforeCapture: async (page) => {
      await page.locator('.o_list_view .o_data_row').first().click();
      await page.waitForSelector('.o_form_view', { timeout: 15000 });
      await page.locator('.o_notebook a.nav-link', { hasText: 'Configuración Fiscal' }).first().click();
      await page.waitForTimeout(600);
    },
    annotations: [],
  },
  {
    name: '08-05-proximos-vencimientos',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '09-01-cartelera-status',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_cartelera_status?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '09-02-documento-form',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_document',
    waitFor: '.o_list_view, .o_kanban_view',
    beforeCapture: async (page) => {
      const newBtn = page.locator('.o_list_button_add, .o-kanban-button-new').first();
      if (await newBtn.count() > 0) {
        await newBtn.click();
        await page.waitForSelector('.o_form_view', { timeout: 15000 });
      }
    },
    annotations: [],
  },
  {
    name: '09-03-evidencia-wizard',
    beforeGoto: (page) => openWizard(page, 'l10n_ve_compliance_manager.action_l10n_ve_cartelera_evidence_wizard', {
      appUrl: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_cartelera_status?view_type=list',
      appWaitFor: '.o_list_view',
      activeIdModel: 'l10n.ve.cartelera.status',
    }),
    waitFor: '.o_dialog .modal-content, .o_dialog .modal-dialog',
    annotations: [],
  },
  {
    name: '10-01-alert-list',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_alert?view_type=list',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '11-01-bandeja-acciones',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon',
    waitFor: '.o_list_view',
    annotations: [],
  },
  {
    name: '11-02-registrar-pago',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon',
    waitFor: '.o_list_view',
    beforeCapture: async (page) => {
      await page.locator('.o_list_view .o_data_row button[name="action_open_payment_wizard"]').first().click();
      await page.waitForSelector('.o_dialog .modal-content, .o_dialog .modal-dialog', { timeout: 15000 });
    },
    annotations: [],
  },
  {
    name: '11-03-analisis-grafico',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_analysis?view_type=graph',
    waitFor: '.o_graph_view, .o_view_graph, .o_content',
    beforeCapture: async (page) => {
      await page.locator('button.o-dropdown:has-text("Medidas")').first().click();
      await page.waitForSelector('.o-dropdown--menu .o_menu_item', { state: 'visible', timeout: 10000 });
      await page.locator('.o-dropdown--menu .o_menu_item').filter({ hasText: /Número/ }).first().click();
      await page.keyboard.press('Escape');
      await page.waitForTimeout(800);
    },
    annotations: [],
  },
  {
    name: '11-04-analisis-pivote',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_analysis?view_type=pivot',
    waitFor: '.o_pivot_view, .o_view_pivot, .o_content',
    beforeCapture: async (page) => {
      await page.locator('button.o-dropdown:has-text("Medidas")').first().click();
      await page.waitForSelector('.o-dropdown--menu .o_menu_item', { state: 'visible', timeout: 10000 });
      await page.locator('.o-dropdown--menu .o_menu_item').filter({ hasText: /Número/ }).first().click();
      await page.keyboard.press('Escape');
      await page.waitForTimeout(800);
    },
    annotations: [],
  },
  {
    name: '11-05-recalcular-vencimiento',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon',
    waitFor: '.o_list_view',
    beforeCapture: async (page) => {
      await page.locator('.o_list_view .o_data_row').first().locator('td.o_data_cell').first().click();
      await page.waitForSelector('.o_form_view', { timeout: 15000 });
    },
    annotations: [
      { selector: 'button[name="action_recalculate_due_dates"]', label: '1' },
    ],
  },
  {
    name: '11-06-acciones-masivas',
    url: '/odoo/action-l10n_ve_compliance_manager.action_l10n_ve_obligation_due_soon',
    waitFor: '.o_list_view',
    beforeCapture: async (page) => {
      const rows = page.locator('.o_list_view .o_data_row');
      const total = Math.min(await rows.count(), 2);
      for (let i = 0; i < total; i += 1) {
        await rows.nth(i).locator('td.o_list_record_selector').click();
      }
      await page.waitForTimeout(400);
      await page.locator('.o_cp_action_menus .dropdown-toggle').first().click();
      await page.waitForSelector('.o-dropdown--menu .dropdown-item', { state: 'visible', timeout: 10000 });
      await page.waitForTimeout(400);
    },
    annotations: [],
  },
];

// === MAIN ===

(async () => {
  if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  try {
    await login(page);
    console.log('✓ login OK');
    await enableAllCompanies(page);
    if (!process.env.SKIP_SEED) {
      await seedDemoData(page);
      await page.waitForTimeout(1500);
      await logout(page);
      await login(page);
      await enableAllCompanies(page);
      console.log('✓ re-login post-seed (refresca compañías permitidas)');
    }
    for (const spec of specs) {
      try {
        await capture(page, spec);
      } catch (err) {
        console.error(`  ✗ ${spec.name} failed: ${err.message}`);
      }
    }
  } finally {
    await browser.close();
  }

  console.log(`\n✓ Done. Screenshots in ${path.relative(process.cwd(), OUT_DIR)}`);
})().catch(err => { console.error(err); process.exit(1); });
