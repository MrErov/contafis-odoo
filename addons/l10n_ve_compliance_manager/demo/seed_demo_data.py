"""Dataset ficticio e idempotente para probar l10n_ve_compliance_manager.

Uso recomendado (dentro del contenedor, sin crear archivos temporales):

    docker compose exec -T web bash -lc \
        "odoo shell -d contea --no-http < /mnt/extra-addons/l10n_ve_compliance_manager/demo/seed_demo_data.py"

El archivo NO está en ``__manifest__``: no se carga en instalaciones normales.
Todos los registros quedan con xmlid ``l10n_ve_compliance_manager_seed.*`` para
que una segunda ejecución actualice/reutilice en vez de duplicar. Ese namespace
no es el del módulo, así que un ``-u`` no los trata como datos obsoletos.
"""

from __future__ import annotations

import base64
from datetime import date, timedelta
from pathlib import Path

from odoo import fields

MODULE = "l10n_ve_compliance_manager"
# Namespace propio para los xmlids del seed. NO usar el namespace del módulo:
# al hacer `-u l10n_ve_compliance_manager`, Odoo borra los registros con xmlid
# de ese módulo que no estén en sus archivos de datos (`ir.model.data._process_end`),
# lo que intentaría borrar clientes/proveedores y chocaría con las facturas.
SEED_NS = "l10n_ve_compliance_manager_seed"
try:
    _HERE = Path(__file__).resolve().parent
except NameError:  # ``odoo shell`` ejecuta stdin con exec() y no define __file__
    import odoo.addons.l10n_ve_compliance_manager as _addon

    _HERE = Path(_addon.__file__).resolve().parent / "demo"

# ---------------------------------------------------------------------------
# Catálogo ficticio
# ---------------------------------------------------------------------------

CLIENTS = [
    {
        "key": "el_sol",
        "name": "Distribuidora El Sol, C.A.",
        "rif": "J-40123456-7",
        "company": 0,
        "is_spe": True,
        "activity": "comercio",
        "municipality": "Libertador",
        "email": "compras@elsol.example.com",
        "phone": "+58 212-5550101",
    },
    {
        "key": "servicios_andinos",
        "name": "Servicios Andinos, S.A.",
        "rif": "J-40987654-3",
        "company": 1,
        "is_spe": False,
        "activity": "servicios",
        "municipality": "Baruta",
        "email": "admin@serviciosandinos.example.com",
        "phone": "+58 212-5550202",
    },
    {
        "key": "maracaibo",
        "name": "Inversiones Maracaibo, C.A.",
        "rif": "J-31555666-9",
        "company": 2,
        "is_spe": False,
        "activity": "mixto",
        "municipality": "Maracaibo",
        "email": "finanzas@inversionesmaracaibo.example.com",
        "phone": "+58 261-5550303",
    },
    {
        "key": "los_andes",
        "name": "Comercial Los Andes, C.A.",
        "rif": "J-31234567-8",
        "company": 0,
        "is_spe": True,
        "activity": "comercio",
        "municipality": "Libertador",
        "email": "contabilidad@losandes.example.com",
        "phone": "+58 212-5550404",
    },
    {
        "key": "caribe",
        "name": "Tecnología Caribe, C.A.",
        "rif": "J-40555111-2",
        "company": 1,
        "is_spe": False,
        "activity": "servicios",
        "municipality": "Baruta",
        "email": "admin@tecnologiacaribe.example.com",
        "phone": "+58 212-5550505",
    },
    {
        "key": "agro_zulia",
        "name": "Agroindustrias del Zulia, C.A.",
        "rif": "J-31666777-4",
        "company": 2,
        "is_spe": True,
        "activity": "industria",
        "municipality": "Maracaibo",
        "email": "tesoreria@agrozulia.example.com",
        "phone": "+58 261-5550606",
    },
]

TYPE_SPECS = [
    {
        "key": "iva_spe",
        "name": "IVA Mensual (SPE)",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "iva",
        "periodicity": "monthly",
        "table": "a1",
        "rule": "1-15",
        "base": "invoice",
        "rate": 16.0,
        "channel": "email",
        "amount": 1250000.0,
    },
    {
        "key": "iva_no_spe",
        "name": "IVA Mensual (No SPE)",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "iva",
        "periodicity": "monthly",
        "table": "none",
        "rule": "dia_fijo",
        "due_day": 15,
        "base": "invoice",
        "rate": 16.0,
        "channel": "email",
        "amount": 980000.0,
    },
    {
        "key": "islr_estimadas",
        "name": "Estimadas de ISLR",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "islr",
        "periodicity": "monthly",
        "table": "est_islr",
        "rule": "dia_fijo",
        "due_day": 15,
        "base": "invoice",
        "rate": 0.0,
        "channel": "email",
        "amount": 360000.0,
    },
    {
        "key": "islr_retenciones",
        "name": "Retenciones de ISLR",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "islr",
        "periodicity": "monthly",
        "table": "ret_islr",
        "rule": "dia_fijo",
        "due_day": 15,
        "base": "purchase",
        "rate": 0.0,
        "channel": "email",
        "amount": 145000.0,
    },
    {
        "key": "retencion_iva",
        "name": "Retención de IVA (75%)",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "iva",
        "periodicity": "monthly",
        "table": "none",
        "rule": "dia_fijo",
        "due_day": 15,
        "base": "purchase",
        "rate": 75.0,
        "channel": "email",
        "amount": 937500.0,
    },
    {
        "key": "retencion_islr",
        "name": "Retención de ISLR (3%)",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "islr",
        "periodicity": "monthly",
        "table": "none",
        "rule": "dia_fijo",
        "due_day": 15,
        "base": "purchase",
        "rate": 3.0,
        "channel": "whatsapp",
        "amount": 145000.0,
    },
    {
        "key": "ivss",
        "name": "IVSS Patronal",
        "institution": "IVSS",
        "category": "parafiscal",
        "tax_type": "ivss",
        "periodicity": "monthly",
        "table": "none",
        "rule": "primeros_5_dias_habiles",
        "base": "payroll",
        "rate": 9.0,
        "channel": "email",
        "amount": 320000.0,
    },
    {
        "key": "inces",
        "name": "INCES",
        "institution": "INCES",
        "category": "parafiscal",
        "tax_type": "inces",
        "periodicity": "trimestral",
        "generation_months": "3,6,9,12",
        "table": "none",
        "rule": "primeros_5_dias_habiles",
        "base": "payroll",
        "rate": 2.0,
        "channel": "email",
        "amount": 95000.0,
    },
    {
        "key": "banavih",
        "name": "BANAVIH (FAOV)",
        "institution": "BANAVIH",
        "category": "parafiscal",
        "tax_type": "banavih",
        "periodicity": "monthly",
        "table": "none",
        "rule": "primeros_5_dias_habiles",
        "base": "payroll",
        "rate": 2.0,
        "channel": "both",
        "amount": 48000.0,
    },
    {
        "key": "iae",
        "name": "Impuesto de Actividades Económicas (IAE)",
        "institution": "Alcaldía",
        "category": "municipal",
        "tax_type": "municipal",
        "periodicity": "monthly",
        "table": "none",
        "rule": "dia_fijo",
        "due_day": 10,
        "base": "gross_income",
        "rate": 0.5,
        "channel": "email",
        "amount": 210000.0,
    },
    {
        "key": "igtf",
        "name": "IGTF",
        "institution": "SENIAT",
        "category": "fiscal_nacional",
        "tax_type": "igtf",
        "periodicity": "monthly",
        "table": "none",
        "rule": "dia_fijo",
        "due_day": 15,
        "base": "purchase",
        "rate": 3.0,
        "channel": "whatsapp",
        "amount": 38000.0,
    },
]

DOC_SPECS = [
    ("C01", 180, "valid"),
    ("C02", 10, "valid"),
    ("C05", None, "valid"),
    ("C08", -20, "expired"),
    ("C10", 120, "valid"),
    ("C16", None, "pending"),
    ("C30", -45, "expired"),
    ("C31", None, "rejected"),
    ("C33", 90, "valid"),
]

SUPPLIERS = [
    ("Suministros Industriales Carabobo, C.A.", "J-30111222-3", "ventas@suministroscarabobo.example.com"),
    ("Transporte y Logística del Centro, C.A.", "J-30222333-4", "facturacion@transportecentro.example.com"),
    ("Papelería y Oficina Los Próceres, C.A.", "J-30333444-5", "admin@papelerialosproceres.example.com"),
    ("Servicios Eléctricos Bolívar, C.A.", "J-30444555-6", "cobranzas@electricosbolivar.example.com"),
]

VAT_PERIODS = ["2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]

ISLR_LINES = [
    (14, "Ventas", "ventas", "income", 1991278.80, 1991278.80, 0.0, "Art. 5 LISLR"),
    (17, "Inventario Inicial de Mercancía", "inventario_inicial", "cost", 193704.75, 193704.75, 0.0, "Art. 23 LISLR"),
    (18, "Compras de Mercancías", "compras_mercancia", "cost", 1788584.01, 1788584.01, 0.0, "Art. 23 LISLR"),
    (24, "Inventario Final", "inventario_final", "cost", 598486.50, 598486.50, 0.0, "Art. 23 LISLR"),
    (28, "Sueldos directivos", "sueldos_directivos", "deduction", 77829.75, 60747.65, 17082.10, "Hasta 10% de ingresos brutos"),
    (29, "Tributos pagados al SENIAT", "tributos_pagados", "deduction", 51096.57, 51096.57, 0.0, "Art. 27 LISLR"),
    (31, "Arrendamientos de inmuebles", "arrendamientos", "deduction", 24500.00, 24500.00, 0.0, "Art. 27 Num. 1 LISLR"),
    (32, "Otros gastos", "otros_gastos", "deduction", 56053.12, 56053.12, 0.0, ""),
    (35, "Gastos de representación", "gastos_representacion", "deduction", 58708.12, 58708.12, 0.0, ""),
    (37, "Gastos de transporte", "gastos_transporte", "deduction", 168954.75, 168954.75, 0.0, ""),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _migrate_legacy_xmlids(env):
    """Mueve los xmlids de versiones previas del seeder a ``SEED_NS``.

    La primera versión registraba los xmlids bajo el namespace del módulo, lo
    que hacía que un ``-u`` los considerara datos obsoletos y borrara los
    registros. Es idempotente y no hace nada si ya están migrados.
    """
    Data = env["ir.model.data"]
    legacy = Data.search([("module", "=", MODULE), ("name", "like", "seed_%")])
    for data in legacy:
        if Data.search_count([("module", "=", SEED_NS), ("name", "=", data.name)]):
            data.unlink()
        else:
            data.write({"module": SEED_NS})


def _register(env, model, name, res_id):
    """Crea o actualiza el xmlid ``SEED_NS.name`` apuntando a ``res_id``."""
    data = env["ir.model.data"].search(
        [("module", "=", SEED_NS), ("name", "=", name)], limit=1
    )
    vals = {
        "module": SEED_NS,
        "name": name,
        "model": model,
        "res_id": res_id,
        "noupdate": False,
    }
    if data:
        data.write({"model": model, "res_id": res_id})
    else:
        env["ir.model.data"].create(vals)


def _ensure(env, model, name, vals, domain=None):
    """Devuelve el registro con xmlid ``SEED_NS.name`` o lo crea/reutiliza."""
    record = env.ref(f"{SEED_NS}.{name}", raise_if_not_found=False)
    if record:
        return record
    if domain:
        record = env[model].search(domain, limit=1)
        if record:
            _register(env, model, name, record.id)
            return record
    record = env[model].create(vals)
    _register(env, model, name, record.id)
    return record


def _country_ve(env):
    country = env.ref("base.ve", raise_if_not_found=False)
    if not country:
        country = env["res.country"].search([("code", "=", "VE")], limit=1)
    return country


def _institution(env, name):
    institution = env["l10n.ve.institution"].search([("name", "=", name)], limit=1)
    return institution or env["l10n.ve.institution"].search([], limit=1)


def _companies(env):
    main = env.ref("base.main_company", raise_if_not_found=False) or env.company
    ordered = []
    seen = set()
    for company in main | env["res.company"].search([], order="id"):
        if company.id not in seen:
            seen.add(company.id)
            ordered.append(company)
    return ordered


def _company_at(companies, index):
    return companies[min(index, len(companies) - 1)]


def _admin(env):
    return env.ref("base.user_admin", raise_if_not_found=False) or env.user


def _image_b64():
    """JPEG válido en base64 (el campo Binary de Odoo 19 usa base64).

    El fixture del repo tiene cabecera JPEG pero está truncado y PIL no puede
    decodificarlo, así que se genera una evidencia sintética en memoria.
    """
    import io

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (480, 640), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 20, 460, 620], outline="#1f4e79", width=4)
    draw.text((44, 60), "EVIDENCIA FISCAL (DEMO)", fill="#1f4e79")
    draw.text((44, 100), "Documento de prueba generado por", fill="#333333")
    draw.text((44, 120), "seed_demo_data.py", fill="#333333")
    draw.line([44, 160, 436, 160], fill="#1f4e79", width=2)
    for row in range(8):
        top = 190 + row * 34
        draw.rectangle([44, top, 250, top + 14], fill="#d9e2f3")
        draw.rectangle([272, top, 436, top + 14], fill="#eeeeee")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Secciones del seed
# ---------------------------------------------------------------------------


def _seed_types(env, currency):
    types = {}
    for spec in TYPE_SPECS:
        institution = _institution(env, spec["institution"])
        vals = {
            "name": spec["name"],
            "institution_id": institution.id if institution else False,
            "category": spec["category"],
            "tax_type": spec["tax_type"],
            "periodicity": spec["periodicity"],
            "generation_months": spec.get("generation_months", False),
            "due_day_rule": spec["rule"],
            "due_day_value": spec.get("due_day", 0),
            "seniat_table_code": spec["table"],
            "base_calculation": spec["base"],
            "rate": spec["rate"],
            "currency_id": currency.id,
            "alert_days_before": 5,
            "alert_channel": spec["channel"],
            "alert_enabled": True,
            "alert_on_overdue": True,
            "alert_on_missing_payment": True,
        }
        types[spec["key"]] = _ensure(
            env,
            "l10n.ve.obligation.type",
            f"seed_type_{spec['key']}",
            vals,
            domain=[("name", "=", spec["name"])],
        )
    return types


def _seed_clients(env, companies, types, country):
    clients = []
    admin = _admin(env)
    for index, spec in enumerate(CLIENTS):
        company = _company_at(companies, spec["company"])
        partner = env["res.partner"].search([("vat", "=", spec["rif"])], limit=1)
        partner_vals = {
            "name": spec["name"],
            "vat": spec["rif"],
            "email": spec["email"],
            "phone": spec["phone"],
            "city": spec["municipality"],
            "country_id": country.id if country else False,
            "company_type": "company",
            "customer_rank": 1,
        }
        if partner:
            _register(env, "res.partner", f"seed_partner_{spec['key']}", partner.id)
            updates = {}
            for field_name in ("email", "phone", "city", "country_id"):
                if not partner[field_name]:
                    updates[field_name] = partner_vals[field_name]
            if updates:
                partner.write(updates)
        else:
            partner = _ensure(
                env,
                "res.partner",
                f"seed_partner_{spec['key']}",
                partner_vals,
                domain=[("vat", "=", spec["rif"])],
            )

        client = env["l10n.ve.compliance.client"].search(
            [("rif", "=", spec["rif"])], limit=1
        )
        keys = _applicable_keys(spec)
        applicable = env["l10n.ve.obligation.type"]
        for key in keys:
            if key in types:
                applicable |= types[key]
        client_vals = {
            "name": spec["name"],
            "partner_id": partner.id,
            "company_id": company.id,
            "accountant_id": admin.id,
            "rif": spec["rif"],
            "is_spe": spec["is_spe"],
            "activity_type": spec["activity"],
            "municipality": spec["municipality"],
            "applicable_type_ids": [(6, 0, applicable.ids)],
        }
        if client:
            _register(
                env, "l10n.ve.compliance.client", f"seed_client_{spec['key']}", client.id
            )
            client.write(
                {
                    "is_spe": spec["is_spe"],
                    "activity_type": spec["activity"],
                    "municipality": spec["municipality"],
                    "applicable_type_ids": [
                        (6, 0, (client.applicable_type_ids | applicable).ids)
                    ],
                }
            )
        else:
            client = env["l10n.ve.compliance.client"].create(client_vals)
            _register(
                env, "l10n.ve.compliance.client", f"seed_client_{spec['key']}", client.id
            )
        clients.append(client)
    return clients


def _applicable_keys(spec):
    keys = [
        "iva_spe" if spec["is_spe"] else "iva_no_spe",
        "islr_estimadas",
        "islr_retenciones",
        "retencion_iva",
        "retencion_islr",
        "ivss",
        "inces",
        "banavih",
    ]
    if spec["activity"] in ("comercio", "mixto"):
        keys.append("iae")
    if spec["key"] in ("servicios_andinos", "maracaibo", "caribe"):
        keys.append("igtf")
    return keys


def _seed_obligations(env, clients, types, today):
    year = 2026
    for client_index, (client, spec) in enumerate(zip(clients, CLIENTS)):
        keys = _applicable_keys(spec)
        for type_index, key in enumerate(keys):
            obligation_type = types.get(key)
            if not obligation_type:
                continue
            spec_type = next(
                (item for item in TYPE_SPECS if item["key"] == key), {}
            )
            base_amount = spec_type.get("amount", 100000.0)
            for month in range(1, 13):
                if obligation_type.periodicity == "trimestral" and month % 3:
                    continue
                if obligation_type.periodicity == "anual" and month != 12:
                    continue
                period = f"{month}/{year}"
                domain = [
                    ("client_id", "=", client.id),
                    ("obligation_type_id", "=", obligation_type.id),
                    ("period", "=", period),
                    ("quincena", "=", "monthly"),
                ]
                xmlid = (
                    f"seed_obligation_{spec['key']}_{key}_{year}_{month:02d}"
                )
                existing = env["l10n.ve.obligation"].search(domain, limit=1)
                if existing:
                    _register(env, "l10n.ve.obligation", xmlid, existing.id)
                    continue

                factor = 1.0 + (client_index * 0.15)
                amount = round(base_amount * factor, 2)
                obligation = env["l10n.ve.obligation"].create(
                    {
                        "name": f"{obligation_type.name} {period}",
                        "client_id": client.id,
                        "obligation_type_id": obligation_type.id,
                        "period": period,
                        "quincena": "monthly",
                        "amount": amount,
                        "currency_id": client.company_id.currency_id.id,
                        "state": "pending",
                        "responsible_id": _admin(env).id,
                        "notes": "Dato ficticio de demostración",
                    }
                )
                _register(env, "l10n.ve.obligation", xmlid, obligation.id)

                due = obligation.due_date or (today + timedelta(days=15))
                seed = (client_index * 7 + type_index * 3 + month) % 11
                state = "pending"
                payment_date = False
                if due <= today:
                    if seed <= 5:
                        state = "paid"
                        payment_date = due - timedelta(days=3)
                    elif seed == 6:
                        state = "overdue"
                        due = today - timedelta(days=4 + seed)
                    elif seed == 7:
                        state = "cancelled"
                    else:
                        state = "pending"
                        due = today + timedelta(days=5 + seed)
                elif seed == 10 and month <= today.month:
                    state = "paid"
                    payment_date = today - timedelta(days=2)

                vals = {"state": state}
                if due != obligation.due_date:
                    vals["due_date"] = due
                if state == "paid":
                    if payment_date and payment_date > today:
                        payment_date = today - timedelta(days=1)
                    vals.update(
                        {
                            "payment_date": payment_date,
                            "payment_reference": f"REF-{period.replace('/', '-')}-{client_index + 1}{type_index + 1}",
                        }
                    )
                if state == "cancelled":
                    vals["notes"] = "Obligación ficticia cancelada"
                obligation.write(vals)


def _seed_documents(env, clients, today):
    doc_types = {
        doc_type.code: doc_type
        for doc_type in env["l10n.ve.document.type"].search(
            [("required_for", "=", "company")]
        )
    }
    for client_index, (client, spec) in enumerate(zip(clients, CLIENTS)):
        for code, days, state in DOC_SPECS:
            doc_type = doc_types.get(code)
            if not doc_type:
                continue
            domain = [
                ("client_id", "=", client.id),
                ("document_type_id", "=", doc_type.id),
            ]
            xmlid = f"seed_document_{spec['key']}_{code}"
            existing = env["l10n.ve.document"].search(domain, limit=1)
            if existing:
                _register(env, "l10n.ve.document", xmlid, existing.id)
                continue

            expiry = today + timedelta(days=days) if days is not None else False
            if expiry:
                issue = expiry - timedelta(days=doc_type.validity_days or 365)
            else:
                issue = today - timedelta(days=60)
            document = env["l10n.ve.document"].create(
                {
                    "client_id": client.id,
                    "partner_id": client.partner_id.id,
                    "document_type_id": doc_type.id,
                    "number": f"{code}-{client_index + 1:02d}-2026",
                    "issue_date": issue,
                    "expiry_date": expiry,
                    "state": state,
                    "notes": "Documento ficticio de demostración",
                }
            )
            _register(env, "l10n.ve.document", xmlid, document.id)


def _seed_cartelera(env):
    status_model = env["l10n.ve.cartelera.status"]
    for month in (9, 10, 11, 12):
        status_model.generate_snapshot_all_clients(2026, str(month))


def _seed_evidence(env, clients):
    image = _image_b64()
    evidence_specs = [
        (0, "C01", "accepted", "Constancia de publicación mercantil"),
        (0, "C02", "pending", "Permiso de bomberos en revisión"),
        (1, "C08", "accepted", "Declaración IVA aceptada"),
        (1, "C30", "rejected", "Licencia ilegible, repetir foto"),
        (2, "C01", "pending", "Publicación mercantil pendiente de validar"),
        (2, "C01", "accepted", "Segunda evidencia válida"),
        (3, "C02", "accepted", "Permiso de bomberos vigente"),
    ]
    statuses = env["l10n.ve.cartelera.status"]
    for index, (client_index, code, state, notes) in enumerate(evidence_specs):
        client = clients[client_index]
        status = statuses.search(
            [
                ("client_id", "=", client.id),
                ("year", "=", 2026),
                ("month", "=", "11"),
                ("document_type_id.code", "=", code),
            ],
            limit=1,
        )
        if not status:
            continue
        filename = f"evidencia_{client.id}_{code}_{index + 1}.jpg"
        evidence = _ensure(
            env,
            "l10n.ve.cartelera.evidence",
            f"seed_evidence_{client_index}_{code}_{index + 1}",
            {
                "cartelera_status_id": status.id,
                "filename": filename,
                "image": image,
                "state": state,
                "uploaded_at": fields.Datetime.now() - timedelta(days=index),
                "notes": notes,
            },
            domain=[
                ("cartelera_status_id", "=", status.id),
                ("filename", "=", filename),
            ],
        )
        statuses |= evidence.cartelera_status_id
    for status in statuses:
        status._recompute_status_from_evidence()


def _seed_suppliers(env, country):
    suppliers = []
    for index, (name, rif, email) in enumerate(SUPPLIERS):
        supplier = env["res.partner"].search([("vat", "=", rif)], limit=1)
        vals = {
            "name": name,
            "vat": rif,
            "email": email,
            "phone": f"+58 212-5551{index:03d}",
            "country_id": country.id if country else False,
            "company_type": "company",
            "supplier_rank": 1,
        }
        if not supplier:
            supplier = _ensure(
                env,
                "res.partner",
                f"seed_supplier_{index + 1}",
                vals,
                domain=[("vat", "=", rif)],
            )
        else:
            _register(env, "res.partner", f"seed_supplier_{index + 1}", supplier.id)
        suppliers.append(supplier)
    return suppliers


def _seed_retentions(env, company, suppliers):
    template = env["account.move"].search(
        [("move_type", "=", "in_invoice"), ("company_id", "=", company.id)],
        order="id desc",
        limit=1,
    )
    journal = template.journal_id if template else env["account.journal"].search(
        [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
    )
    tax = env["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "purchase"),
            ("amount", "=", 16.0),
        ],
        limit=1,
    )
    account = (
        template.invoice_line_ids[:1].account_id
        if template and template.invoice_line_ids
        else False
    )
    if not (journal and tax and account and suppliers):
        print("SEED_WARN: sin plantilla contable para retenciones")
        return

    bill_specs = [
        (0, 1200.0, date(2026, 9, 15), "SERVICIOS DE MANTENIMIENTO"),
        (1, 950.0, date(2026, 9, 22), "FLETES NACIONALES"),
        (2, 2400.0, date(2026, 10, 5), "PAPELERÍA Y ÚTILES"),
        (3, 780.0, date(2026, 10, 12), "REPARACIÓN ELÉCTRICA"),
        (0, 1600.0, date(2026, 10, 20), "REPUESTOS INDUSTRIALES"),
        (1, 3000.0, date(2026, 11, 2), "LOGÍSTICA DE DESPACHO"),
    ]
    for index, (supplier_index, amount, invoice_date, label) in enumerate(bill_specs):
        supplier = suppliers[supplier_index]
        ref = f"SEED-FC-{index + 1:02d}"
        move = env["account.move"].search(
            [("ref", "=", ref), ("move_type", "=", "in_invoice")], limit=1
        )
        if not move:
            move = env["account.move"].create(
                {
                    "move_type": "in_invoice",
                    "partner_id": supplier.id,
                    "company_id": company.id,
                    "journal_id": journal.id,
                    "currency_id": company.currency_id.id,
                    "invoice_date": invoice_date,
                    "date": invoice_date,
                    "ref": ref,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": f"{label} (dato ficticio)",
                                "quantity": 1.0,
                                "price_unit": amount,
                                "account_id": account.id,
                                "tax_ids": [(6, 0, [tax.id])],
                            },
                        )
                    ],
                }
            )
            try:
                move.action_post()
            except Exception as error:  # pragma: no cover - depende del plan contable
                print(f"SEED_WARN: no se pudo publicar {ref}: {error}")

        retentions = env["l10n.ve.retention.service"].generate_retentions(move)
        for retention_index, retention in enumerate(retentions):
            _register(
                env,
                "l10n.retention",
                f"seed_retention_{index + 1}_{retention_index + 1}",
                retention.id,
            )
            if index % 2 == 0 and retention.state == "draft":
                retention.action_post()


def _seed_vat_book(env, companies, clients, suppliers):
    purchase_specs = [
        (15000.0, 16.0, "33"),
        (8500.0, 8.0, "333"),
        (22000.0, 16.0, "30"),
        (12000.0, 16.0, "31"),
    ]
    sale_specs = [
        (18000.0, 16.0, "42"),
        (9500.0, 8.0, "443"),
        (7200.0, 0.0, "40"),
    ]
    for company in companies[:3]:
        for period in VAT_PERIODS:
            for index, (base, rate, operation) in enumerate(purchase_specs):
                supplier = suppliers[index % len(suppliers)]
                vat = round(base * rate / 100.0, 2)
                vals = {
                    "book_type": "purchase",
                    "period_month": period,
                    "partner_id": supplier.id,
                    "invoice_number": f"FC-{company.id}-{period.replace('-', '')}-{index + 1}",
                    "control_number": f"00-{company.id}{period[-2:]}{index + 1:03d}",
                    "operation_code": operation,
                    "total_with_vat": round(base + vat, 2),
                    "company_id": company.id,
                    "source": "manual",
                    "retention_direction": "to_vendor",
                }
                if operation == "30":
                    vals.update(
                        {
                            "base_no_credit": base,
                            "vat_general": 0.0,
                            "total_with_vat": base,
                        }
                    )
                elif operation == "31":
                    vals.update({"base_import_16": base, "vat_import_16": vat})
                elif operation == "333":
                    vals.update({"base_reduced": base, "vat_reduced": vat})
                else:
                    vals.update({"base_general": base, "vat_general": vat})
                if index == 0:
                    vals.update(
                        {
                            "retention_number": f"RET-{company.id}-{period}-01",
                            "vat_retained": round(vat * 0.75, 2),
                        }
                    )
                _ensure(
                    env,
                    "l10n.ve.vat.book.line",
                    f"seed_vat_purchase_{company.id}_{period.replace('-', '')}_{index + 1}",
                    vals,
                    domain=[
                        ("company_id", "=", company.id),
                        ("period_month", "=", period),
                        ("book_type", "=", "purchase"),
                        ("invoice_number", "=", vals["invoice_number"]),
                    ],
                )

            for index, (base, rate, operation) in enumerate(sale_specs):
                client = clients[index % len(clients)]
                vat = round(base * rate / 100.0, 2)
                vals = {
                    "book_type": "sale",
                    "period_month": period,
                    "partner_id": client.partner_id.id,
                    "invoice_number": f"FV-{company.id}-{period.replace('-', '')}-{index + 1}",
                    "control_number": f"00-{company.id}{period[-2:]}9{index + 1:02d}",
                    "operation_code": operation,
                    "total_with_vat": round(base + vat, 2),
                    "company_id": company.id,
                    "source": "manual",
                    "retention_direction": "by_buyer",
                }
                if operation == "40":
                    vals.update(
                        {
                            "base_not_subject": base,
                            "vat_general": 0.0,
                            "total_with_vat": base,
                        }
                    )
                elif operation == "443":
                    vals.update({"base_reduced": base, "vat_reduced": vat})
                else:
                    vals.update({"base_general": base, "vat_general": vat})
                if index == 0:
                    vals.update(
                        {
                            "retention_number": f"RET-V-{company.id}-{period}-01",
                            "vat_retained": round(vat * 0.75, 2),
                        }
                    )
                _ensure(
                    env,
                    "l10n.ve.vat.book.line",
                    f"seed_vat_sale_{company.id}_{period.replace('-', '')}_{index + 1}",
                    vals,
                    domain=[
                        ("company_id", "=", company.id),
                        ("period_month", "=", period),
                        ("book_type", "=", "sale"),
                        ("invoice_number", "=", vals["invoice_number"]),
                    ],
                )


def _seed_vat_returns(env, companies):
    for company in companies[:3]:
        for period in VAT_PERIODS:
            vat_return = _ensure(
                env,
                "l10n.ve.vat.return",
                f"seed_vat_return_{company.id}_{period.replace('-', '')}",
                {
                    "period_month": period,
                    "company_id": company.id,
                    "state": "draft",
                },
                domain=[
                    ("company_id", "=", company.id),
                    ("period_month", "=", period),
                ],
            )
            try:
                vat_return.action_load_from_book()
                vat_return.action_calculate()
            except Exception as error:  # pragma: no cover - datos incompletos
                print(f"SEED_WARN: declaración {company.id}/{period}: {error}")


def _seed_alerts(env, today):
    now = fields.Datetime.now()
    overdue = env["l10n.ve.obligation"].search(
        [("state", "=", "overdue")], order="due_date", limit=6
    )
    due_soon = env["l10n.ve.obligation"].search(
        [
            ("state", "=", "pending"),
            ("due_date", "!=", False),
            ("due_date", "<=", today + timedelta(days=15)),
        ],
        order="due_date",
        limit=4,
    )
    documents = env["l10n.ve.document"].search(
        [
            ("state", "=", "valid"),
            ("expiry_date", "!=", False),
            ("expiry_date", "<=", today + timedelta(days=30)),
        ],
        order="expiry_date",
        limit=4,
    )

    specs = []
    for index, obligation in enumerate(overdue):
        specs.append(
            (
                f"seed_alert_overdue_{index + 1}",
                {
                    "name": f"{obligation.client_id.name} - Obligación vencida",
                    "client_id": obligation.client_id.id,
                    "obligation_id": obligation.id,
                    "alert_type": "overdue",
                    "state": "pending" if index % 2 else "sent",
                    "channel": "email" if index % 2 else "whatsapp",
                    "recipient_ids": [(6, 0, [obligation.client_id.partner_id.id])],
                    "message": f"La obligación {obligation.name} venció el {obligation.due_date}.",
                    "date": now - timedelta(days=index + 1),
                },
            )
        )
    for index, obligation in enumerate(due_soon):
        specs.append(
            (
                f"seed_alert_due_soon_{index + 1}",
                {
                    "name": f"{obligation.client_id.name} - Vence pronto",
                    "client_id": obligation.client_id.id,
                    "obligation_id": obligation.id,
                    "alert_type": "due_soon",
                    "state": "done" if index % 2 else "pending",
                    "channel": "email",
                    "recipient_ids": [(6, 0, [obligation.client_id.partner_id.id])],
                    "message": f"La obligación {obligation.name} vence el {obligation.due_date}.",
                    "date": now - timedelta(days=index + 2),
                },
            )
        )
    for index, document in enumerate(documents):
        specs.append(
            (
                f"seed_alert_document_{index + 1}",
                {
                    "name": f"{document.client_id.name} - Documento por vencer",
                    "client_id": document.client_id.id,
                    "document_id": document.id,
                    "alert_type": "document_expiring",
                    "state": "pending",
                    "channel": "whatsapp" if index % 2 else "email",
                    "recipient_ids": [(6, 0, [document.client_id.partner_id.id])],
                    "message": f"El documento {document.number} vence el {document.expiry_date}.",
                    "date": now - timedelta(days=index + 3),
                },
            )
        )

    first_client = env["l10n.ve.compliance.client"].search([], order="id", limit=1)
    for index in range(2):
        specs.append(
            (
                f"seed_alert_manual_{index + 1}",
                {
                    "name": f"{first_client.name} - Revisión manual",
                    "client_id": first_client.id,
                    "alert_type": "manual",
                    "state": "pending",
                    "channel": "email",
                    "recipient_ids": [(6, 0, [first_client.partner_id.id])],
                    "message": "Alerta manual ficticia para probar el flujo de alertas.",
                    "date": now - timedelta(days=index + 5),
                },
            )
        )

    for xmlid, vals in specs:
        alert = _ensure(env, "l10n.ve.alert", xmlid, vals)
        if alert.state in ("sent", "done") and not alert.sent_date:
            alert.write({"sent_date": alert.date})


def _seed_islr(env, clients):
    for client_index in (0, 3):
        if client_index >= len(clients):
            continue
        client = clients[client_index]
        factor = 1.0 + client_index * 0.12
        totals = {
            "total_ingresos": {
                "accounting": round(1991278.80 * factor, 2),
                "fiscal": round(1991278.80 * factor, 2),
            },
            "mercancia_disponible": {
                "accounting": round(1982288.76 * factor, 2),
                "fiscal": round(1982288.76 * factor, 2),
            },
            "total_costo_venta": {
                "accounting": round(1383802.26 * factor, 2),
                "fiscal": round(1383802.26 * factor, 2),
            },
            "renta_bruta": {
                "accounting": round(607476.54 * factor, 2),
                "fiscal": round(607476.54 * factor, 2),
            },
            "total_deducciones": {
                "accounting": round(184979.44 * factor, 2),
                "fiscal": round(395560.22 * factor, 2),
            },
            "utilidad_neta": {
                "accounting": round(422497.10 * factor, 2),
                "fiscal": round(211916.32 * factor, 2),
            },
        }
        reconciliation = _ensure(
            env,
            "l10n.ve.islr.reconciliation",
            f"seed_islr_recon_{CLIENTS[client_index]['key']}_2025",
            {
                "client_id": client.id,
                "company_id": client.company_id.id,
                "fiscal_year": 2025,
                "state": "draft",
                "monto_a_pagar_xlsx": round(47863.69 * factor, 2),
                "totals_xlsx": totals,
                "import_meta": {
                    "source_file": "CONCILIACION_FINANCIERA_Y_FISCAL_DEMO_2026.xlsx",
                    "imported_by": "seed_demo_data",
                    "imported_at": "2026-10-01T09:30:00",
                    "duplicates": [],
                    "text_cells": [],
                },
            },
            domain=[("client_id", "=", client.id), ("fiscal_year", "=", 2025)],
        )
        for sequence, label, code, category, accounting, fiscal, not_deductible, legal in ISLR_LINES:
            _ensure(
                env,
                "l10n.ve.islr.reconciliation.line",
                f"seed_islr_line_{CLIENTS[client_index]['key']}_{code}",
                {
                    "reconciliation_id": reconciliation.id,
                    "sequence": sequence,
                    "label": label,
                    "code": code,
                    "category": category,
                    "amount_accounting": round(accounting * factor, 2),
                    "amount_fiscal": round(fiscal * factor, 2),
                    "amount_not_deductible": round(not_deductible * factor, 2),
                    "legal_basis": legal or False,
                },
                domain=[
                    ("reconciliation_id", "=", reconciliation.id),
                    ("code", "=", code),
                ],
            )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


def run(env, commit=False):
    """Crea el dataset. ``commit=True`` solo para ejecución desde odoo shell."""
    today = fields.Date.today()
    _migrate_legacy_xmlids(env)
    country = _country_ve(env)
    companies = _companies(env)
    currency = companies[0].currency_id

    types = _seed_types(env, currency)
    clients = _seed_clients(env, companies, types, country)
    _seed_obligations(env, clients, types, today)
    _seed_documents(env, clients, today)
    _seed_cartelera(env)
    _seed_evidence(env, clients)
    suppliers = _seed_suppliers(env, country)
    _seed_retentions(env, companies[0], suppliers)
    _seed_vat_book(env, companies, clients, suppliers)
    _seed_vat_returns(env, companies)
    _seed_alerts(env, today)
    _seed_islr(env, clients)

    if commit:
        env.cr.commit()

    counts = {
        "clients": env["l10n.ve.compliance.client"].search_count([]),
        "obligations": env["l10n.ve.obligation"].search_count([]),
        "documents": env["l10n.ve.document"].search_count([]),
        "cartelera": env["l10n.ve.cartelera.status"].search_count([]),
        "evidence": env["l10n.ve.cartelera.evidence"].search_count([]),
        "retentions": env["l10n.retention"].search_count([]),
        "vat_book_lines": env["l10n.ve.vat.book.line"].search_count([]),
        "vat_returns": env["l10n.ve.vat.return"].search_count([]),
        "alerts": env["l10n.ve.alert"].search_count([]),
        "islr_reconciliations": env["l10n.ve.islr.reconciliation"].search_count([]),
    }
    print("SEED_OK " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return counts


if "env" in globals():
    run(globals()["env"], commit=True)
